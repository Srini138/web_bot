import logging
import re
import time
import warnings
from typing import List, Optional, Tuple, Union, cast
from nemoguardrails import LLMRails
from nemoguardrails.actions.llm.utils import get_colang_history
from nemoguardrails.colang.v1_0.runtime.flows import compute_context
from nemoguardrails.colang.v2_x.runtime.flows import  State
from nemoguardrails.colang.v2_x.runtime.runtime import RuntimeV2_x
from nemoguardrails.colang.v2_x.runtime.serialization import (
    json_to_state,
    state_to_json,
)
from nemoguardrails.context import (
    explain_info_var,
    generation_options_var,
    llm_stats_var,
    streaming_handler_var,
)
from nemoguardrails.logging.explain import ExplainInfo
from nemoguardrails.logging.processing_log import compute_generation_log
from nemoguardrails.logging.stats import LLMStats
from nemoguardrails.rails.llm.options import (
    GenerationLog,
    GenerationOptions,
    GenerationResponse,
)
from nemoguardrails.rails.llm.utils import get_history_cache_key
from nemoguardrails.streaming import StreamingHandler


log = logging.getLogger(__name__)


class MyRails(LLMRails):
    async def generate_async(
            self,
            prompt: Optional[str] = None,
            messages: Optional[List[dict]] = None,
            options: Optional[Union[dict, GenerationOptions]] = None,
            state: Optional[Union[dict, State]] = None,
            streaming_handler: Optional[StreamingHandler] = None,
            return_context: bool = False,
    ) -> Union[str, dict, GenerationResponse, Tuple[dict, dict]]:

        # If a state object is specified, then we switch to "generation options" mode.
        # This is because we want the output to be a GenerationResponse which will contain
        # the output state.
        if state is not None:
            # We deserialize the state if needed.
            if isinstance(state, dict) and state.get("version", "1.0") == "2.x":
                state = json_to_state(state["state"])

            if options is None:
                options = GenerationOptions()

        # We allow options to be specified both as a dict and as an object.
        if options and isinstance(options, dict):
            options = GenerationOptions(**options)

        # Save the generation options in the current async context.
        generation_options_var.set(options)

        if return_context:
            warnings.warn(
                "The `return_context` argument is deprecated and will be removed in 0.9.0. "
                "Use `GenerationOptions.output_vars = True` instead.",
                DeprecationWarning,
                stacklevel=2,
            )

            # And we use the generation options mechanism instead.
            if options is None:
                options = GenerationOptions()
            options.output_vars = True

        if streaming_handler:
            streaming_handler_var.set(streaming_handler)

        # Initialize the object with additional explanation information.
        # We allow this to also be set externally. This is useful when multiple parallel
        # requests are made.
        explain_info = explain_info_var.get()
        if explain_info is None:
            explain_info = ExplainInfo()
            explain_info_var.set(explain_info)

            # We also keep a general reference to this object
            self.explain_info = explain_info

        if prompt is not None:
            # Currently, we transform the prompt request into a single turn conversation
            messages = [{"role": "user", "content": prompt}]

        # If we have generation options, we also add them to the context
        if options:
            messages = [
                           {"role": "context", "content": {"generation_options": options.dict()}}
                       ] + messages

        # If the last message is from the assistant, rather than the user, then
        # we move that to the `$bot_message` variable. This is to enable a more
        # convenient interface. (only when dialog rails are disabled)
        if (
                messages[-1]["role"] == "assistant"
                and options
                and options.rails.dialog is False
        ):
            # We already have the first message with a context update, so we use that
            messages[0]["content"]["bot_message"] = messages[-1]["content"]
            messages = messages[0:-1]

        # TODO: Add support to load back history of events, next to history of messages
        #   This is important as without it, the LLM prediction is not as good.

        t0 = time.time()

        # Initialize the LLM stats
        llm_stats = LLMStats()
        llm_stats_var.set(llm_stats)
        processing_log = []

        # The array of events corresponding to the provided sequence of messages.
        events = self._get_events_for_messages(messages, state)

        if self.config.colang_version == "1.0":
            # If we had a state object, we also need to prepend the events from the state.
            state_events = []
            if state:
                assert isinstance(state, dict)
                state_events = state["events"]

            # Compute the new events.
            new_events = await self.runtime.generate_events(
                state_events + events, processing_log=processing_log
            )
            output_state = None
        else:
            # In generation mode, by default the bot response is an instant action.
            instant_actions = ["UtteranceBotAction"]
            if self.config.rails.actions.instant_actions is not None:
                instant_actions = self.config.rails.actions.instant_actions

            # Cast this explicitly to avoid certain warnings
            runtime: RuntimeV2_x = cast(RuntimeV2_x, self.runtime)

            # Compute the new events.
            # In generation mode, the processing is always blocking, i.e., it waits for
            # all local actions (sync and async).
            new_events, output_state = await runtime.process_events(
                events, state=state, instant_actions=instant_actions, blocking=True
            )
            # We also encode the output state as a JSON
            output_state = {"state": state_to_json(output_state), "version": "2.x"}

        # Extract and join all the messages from StartUtteranceBotAction events as the response.
        responses = []
        response_tool_calls = []
        response_events = []
        new_extra_events = []

        # The processing is different for Colang 1.0 and 2.0
        if self.config.colang_version == "1.0":
            for event in new_events:
                if event["type"] == "StartUtteranceBotAction":
                    # Check if we need to remove a message
                    if event["script"] == "(remove last message)":
                        responses = responses[0:-1]
                    else:
                        responses.append(event["script"])
        else:
            for event in new_events:
                start_action_match = re.match(r"Start(.*Action)", event["type"])

                if start_action_match:
                    action_name = start_action_match[1]
                    # TODO: is there an elegant way to extract just the arguments?
                    arguments = {
                        k: v
                        for k, v in event.items()
                        if k != "type"
                           and k != "uid"
                           and k != "event_created_at"
                           and k != "source_uid"
                           and k != "action_uid"
                    }
                    response_tool_calls.append(
                        {
                            "id": event["action_uid"],
                            "type": "function",
                            "function": {"name": action_name, "arguments": arguments},
                        }
                    )

                elif event["type"] == "UtteranceBotActionFinished":
                    responses.append(event["final_script"])
                else:
                    # We just append the event
                    response_events.append(event)
        print("m",responses)
        try:
            new_message = {"role": "assistant", "content": responses[0]['answer'],"source_documents": responses[0]['source_documents']}
        except:
            new_message = {"role": "assistant", "content": "\n".join(responses)}
        if response_tool_calls:
            new_message["tool_calls"] = response_tool_calls
        if response_events:
            new_message["events"] = response_events

        if self.config.colang_version == "1.0":
            events.extend(new_events)
            events.extend(new_extra_events)

            # If a state object is not used, then we use the implicit caching
            if state is None:
                # Save the new events in the history and update the cache
                cache_key = get_history_cache_key(messages + [new_message])
                self.events_history_cache[cache_key] = events
            else:
                output_state = {"events": events}

        # If logging is enabled, we log the conversation
        # TODO: add support for logging flag
        explain_info.colang_history = get_colang_history(events)
        if self.verbose:
            log.info(f"Conversation history so far: \n{explain_info.colang_history}")

        total_time = time.time() - t0
        log.info(
            "--- :: Total processing took %.2f seconds. LLM Stats: %s"
            % (total_time, llm_stats)
        )

        # If there is a streaming handler, we make sure we close it now
        streaming_handler = streaming_handler_var.get()
        if streaming_handler:
            # print("Closing the stream handler explicitly")
            await streaming_handler.push_chunk(None)

        # If we have generation options, we prepare a GenerationResponse instance.
        if options:
            # If a prompt was used, we only need to return the content of the message.
            if prompt:
                res = GenerationResponse(response=new_message["content"])
            else:
                res = GenerationResponse(response=[new_message])

            if self.config.colang_version == "1.0":
                # If output variables are specified, we extract their values
                if options.output_vars:
                    context = compute_context(events)
                    if isinstance(options.output_vars, list):
                        # If we have only a selection of keys, we filter to only that.
                        res.output_data = {
                            k: context.get(k) for k in options.output_vars
                        }
                    else:
                        # Otherwise, we return the full context
                        res.output_data = context

                    # If the `return_context` is used, then we return a tuple to keep
                    # the interface compatible.
                    # TODO: remove this in 0.10.0.
                    if return_context:
                        return new_message, context

                _log = compute_generation_log(processing_log)

                # Include information about activated rails and LLM calls if requested
                if options.log.activated_rails or options.log.llm_calls:
                    res.log = GenerationLog()

                    # We always include the stats
                    res.log.stats = _log.stats

                    if options.log.activated_rails:
                        res.log.activated_rails = _log.activated_rails

                    if options.log.llm_calls:
                        res.log.llm_calls = []
                        for activated_rail in _log.activated_rails:
                            for executed_action in activated_rail.executed_actions:
                                res.log.llm_calls.extend(executed_action.llm_calls)

                # Include internal events if requested
                if options.log.internal_events:
                    if res.log is None:
                        res.log = GenerationLog()

                    res.log.internal_events = new_events

                # Include the Colang history if requested
                if options.log.colang_history:
                    if res.log is None:
                        res.log = GenerationLog()

                    res.log.colang_history = get_colang_history(events)

                # Include the raw llm output if requested
                if options.llm_output:
                    # Currently, we include the output from the generation LLM calls.
                    for activated_rail in _log.activated_rails:
                        if activated_rail.type == "generation":
                            for executed_action in activated_rail.executed_actions:
                                for llm_call in executed_action.llm_calls:
                                    res.llm_output = llm_call.raw_response
            else:
                if options.output_vars:
                    raise ValueError(
                        "The `output_vars` option is not supported for Colang 2.0 configurations."
                    )

                if (
                        options.log.activated_rails
                        or options.log.llm_calls
                        or options.log.internal_events
                        or options.log.colang_history
                ):
                    raise ValueError(
                        "The `log` option is not supported for Colang 2.0 configurations."
                    )

                if options.llm_output:
                    raise ValueError(
                        "The `llm_output` option is not supported for Colang 2.0 configurations."
                    )

            # Include the state
            if state is not None:
                res.state = output_state

            return res
        else:
            # If a prompt is used, we only return the content of the message.
            if prompt:
                return new_message["content"]
            else:
                return new_message
