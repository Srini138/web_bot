class Chatbox {
    constructor() {
        this.args = {
            openButton: document.querySelector('.chatbox__button'),
            chatBox: document.querySelector('.chatbox__support'),
            sendButton: document.querySelector('.send__button'),
            closeIcon: document.querySelector('.close-icon')
        };

        this.state = false;
        this.messages = [];
    }

    display() {
        const { openButton, chatBox, sendButton, closeIcon } = this.args;

        // Event listener for opening and closing the chatbox
        openButton.addEventListener('click', () => this.toggleState());
        closeIcon.addEventListener('click', () => this.toggleState());

        // Event listener for sending a message
        sendButton.addEventListener('click', () => this.onSendButton());

        // Event listener for pressing the Enter key to send a message
        const inputField = chatBox.querySelector('input');
        inputField.addEventListener('keyup', ({ key }) => {
            if (key === 'Enter') {
                this.onSendButton();
            }
        });

        // Display a default welcome message when the chatbox is initialized
        const welcomeMsg = {
            name: 'Bot',
            message: 'Hello and welcome! What would you like to know about Schneider Electric?',
            timestamp: new Date().toLocaleTimeString('en-US', { hour: 'numeric', minute: 'numeric', hour12: true })
        };
        this.messages.push(welcomeMsg);
        this.updateChatText();
    }

    toggleState() {
        this.state = !this.state;

        // Toggle chatbox visibility
        if (this.state) {
            this.args.chatBox.classList.add('chatbox--active');
        } else {
            this.args.chatBox.classList.remove('chatbox--active');
        }

        // Update the chatbox button image
        const openButton = this.args.openButton.querySelector('img');
        openButton.src = this.state ? 'static/images/down.png' : 'static/images/initbot.png';
    }

    onSendButton() {
        const inputField = this.args.chatBox.querySelector('input');
        const userMessage = inputField.value;

        if (userMessage.trim() === '') {
            return;
        }

        // Add user message with timestamp
        const userMsg = {
            name: 'User',
            message: userMessage,
            timestamp: new Date().toLocaleTimeString('en-US', { hour: 'numeric', minute: 'numeric', hour12: true })
        };
        this.messages.push(userMsg);
        this.updateChatText();

        // Clear the input field
        inputField.value = '';

        // Add typing indicator
        const typingMsg = {
            name: 'Bot',
            message: '...',
            timestamp: new Date().toLocaleTimeString('en-US', { hour: 'numeric', minute: 'numeric', hour12: true })
        };
        this.messages.push(typingMsg);
        this.updateChatText();

        // Simulate typing animation
        let dotCounter = 1;
        const typingInterval = setInterval(() => {
            // Update typing message with dots
            this.messages[this.messages.length - 1].message = '.'.repeat(dotCounter);
            this.updateChatText();

            dotCounter = (dotCounter % 3) + 1;
        }, 500);

        // Fetch the response from the server
        fetch('/get_response', {
            method: 'POST',
            body: JSON.stringify({ message: userMessage }),
            mode: 'cors',
            headers: {
                'Content-Type': 'application/json'
            }
        })
            .then(response => response.json())
            .then(data => {
                // Clear the typing interval
                clearInterval(typingInterval);

                // Replace typing message with bot response
                this.messages[this.messages.length - 1] = {
                    name: 'Bot',
                    message: data.response,
                    timestamp: new Date().toLocaleTimeString('en-US', { hour: 'numeric', minute: 'numeric', hour12: true }),
                    displayDropdown: true,
                    sourceDocs: data.source_docs
                };
                this.updateChatText();
            })
            .catch(error => {
                console.error('Error:', error);
                clearInterval(typingInterval);
            });
    }

    updateChatText() {
        const chatMessages = this.args.chatBox.querySelector('.chatbox__messages');
        let html = '';

        // Iterate through messages in reverse order
        for (let i = this.messages.length - 1; i >= 0; i--) {
            const { name, message, timestamp, displayDropdown, sourceDocs } = this.messages[i];
            console.log(sourceDocs);
            if (name === 'Bot') {
                // Bot message
                html += `<div class="messages__item messages__item--visitor">
                            <div class="bot-image-container">
                                <img class="bot-image" src="static/images/MM.png" alt="Bot Image">
                            </div>
                            <div class="message-content">${message}</div>
                            <div class="message-time">
                                <span class="timestamp">${timestamp}</span>`;

                // Display dropdown icon and links if specified
                if (displayDropdown && sourceDocs && sourceDocs.length > 0) {
                    html += `<button class="dropdown-button">
                                <i class='bx bx-caret-down'></i> Sources
                            </button>
                            <div class="dropdown-links" style="display: none;">`;

                    // Add dropdown links
                    sourceDocs.forEach(source => {
                        html += `<a href="${source}" target="_blank" style="display: block; overflow: hidden; white-space: nowrap; text-overflow: ellipsis;">${source}</a>`;
                    });

                    html += `</div>`; // Close dropdown-links div
                }

                html += `</div>
                        </div>`;
            } else {
                // User message
                html += `<div class="messages__item messages__item--operator">
                            <div class="message-content">${message}</div>
                            <div class="message-time" style="text-align: right;">${timestamp}</div>
                        </div>`;
            }
        }

        // Update chat messages container with generated HTML
        chatMessages.innerHTML = html;

        // Add event listener for dropdown buttons
        chatMessages.querySelectorAll('.dropdown-button').forEach(button => {
            button.addEventListener('click', () => {
                const dropdown = button.nextElementSibling;
                dropdown.style.display = dropdown.style.display === 'block' ? 'none' : 'block';
            });
        });
    }
}

// Create a new Chatbox instance and initialize its display
const chatbox = new Chatbox();
chatbox.display();



