let currentChatId = localStorage.getItem('currentChatId');
let isShowingArchived = false;
const chatMessages = document.getElementById('chat-messages');
const userInput = document.getElementById('user-input');
const sendButton = document.getElementById('send-button');
let isDarkMode = localStorage.getItem('darkMode') === 'true';
let isInitialLoad = true;
let apiKey = localStorage.getItem('apiKey');
let hfApiKey = localStorage.getItem('hfApiKey');

// Function to save chat message
function saveChat(message, isUser, imageData = null) {
    let chats = JSON.parse(localStorage.getItem('chats') || '[]');
    const timestamp = new Date().toISOString();
    
    if (!currentChatId) {
        // Create new chat
        currentChatId = 'chat_' + Date.now();
        const newChat = {
            id: currentChatId,
            title: message.split(' ').slice(0, 2).join(' ') + '...',
            messages: [],
            archived: false,
            timestamp: timestamp
        };
        chats.unshift(newChat);
        localStorage.setItem('currentChatId', currentChatId);
    }

    // Find current chat and add message
    const currentChat = chats.find(chat => chat.id === currentChatId);
    if (currentChat) {
        currentChat.messages.push({
            content: message,
            isUser: isUser,
            timestamp: timestamp,
            imageData: imageData // Store image data if present
        });
        localStorage.setItem('chats', JSON.stringify(chats));
        loadChatHistory();
    }
}

// Function to send message
async function sendMessage() {
    const userInput = document.getElementById('user-input');
    const message = userInput.value.trim();
    if (!message) return;

    if (!localStorage.getItem('apiKey')) {
        showToast('Please set your API key in settings');
        return;
    }

    // Clear input and disable send button
    userInput.value = '';
    userInput.style.height = 'auto';
    document.getElementById('send-button').disabled = true;

    // Display user message
    appendMessage(message, true, true);

    try {
        // Show typing indicator
        showTypingIndicator();

        const response = await fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: message,
                api_key: localStorage.getItem('apiKey'),
                hf_api_key: localStorage.getItem('hfApiKey')
            })
        });

        const contentType = response.headers.get("content-type");
        if (!contentType || !contentType.includes("application/json")) {
            throw new Error("Server returned non-JSON response");
        }

        const data = await response.json();
        
        // Remove typing indicator
        removeTypingIndicator();

        if (!response.ok) {
            throw new Error(data.error || 'Server error occurred');
        }

        // Display bot response
        if (data.response) {
            appendMessage(data.response, false, false, data.image);
        }

        // Save chat history
        saveChat(message, true);
        if (data.response) {
            saveChat(data.response, false, data.image); // Save with image data
        }

    } catch (error) {
        console.error('Error:', error);
        removeTypingIndicator();
        const errorMessage = error.message || 'Sorry, I encountered an error. Please try again.';
        appendMessage(errorMessage, false, true);
    } finally {
        // Re-enable send button
        document.getElementById('send-button').disabled = false;
    }

    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Function to load chat history
function loadChatHistory() {
    const historyList = document.getElementById('history-list');
    const chats = JSON.parse(localStorage.getItem('chats') || '[]');
    
    historyList.innerHTML = '';
    
    // Filter chats based on archive status
    const filteredChats = chats.filter(chat => 
        isShowingArchived ? chat.archived : !chat.archived
    );

    filteredChats.forEach(chat => {
        const historyItem = createHistoryItem(chat);
        if (historyItem) {
            if (chat.id === currentChatId) {
                historyItem.classList.add('active');
            }
            historyList.appendChild(historyItem);
        }
    });

    // Update archive button text
    const toggleArchivedBtn = document.getElementById('toggle-archived');
    if (toggleArchivedBtn) {
        toggleArchivedBtn.querySelector('span').textContent = 
            isShowingArchived ? 'Show active chats' : 'Show archived chats';
    }
}

// Function to load specific chat
function loadChat(chatId) {
    const chats = JSON.parse(localStorage.getItem('chats') || '[]');
    const chat = chats.find(c => c.id === chatId);
    
    if (chat) {
        currentChatId = chatId;
        localStorage.setItem('currentChatId', chatId);
        
        // Clear and load messages
        const chatMessages = document.getElementById('chat-messages');
        chatMessages.innerHTML = '';
        
        if (chat.messages && chat.messages.length > 0) {
            // Pass skipTyping=true when loading chat history
            chat.messages.forEach(msg => {
                appendMessage(msg.content, msg.isUser, true, msg.imageData);
            });
        }
        
        // Update active state in sidebar
        document.querySelectorAll('.history-item').forEach(item => {
            item.classList.remove('active');
            if (item.dataset.chatId === chatId) {
                item.classList.add('active');
            }
        });

        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}

// Function to append message to chat
async function appendMessage(content, isUser, skipTyping = false, imageBase64 = null) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${isUser ? 'user-message' : 'bot-message'}`;
    
    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';

    // Format user messages
    if (isUser) {
        // Handle URLs
        let processedContent = content.replace(
            /(https?:\/\/[^\s]+)/g, 
            '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>'
        );
        
        // Handle email addresses
        processedContent = processedContent.replace(
            /([a-zA-Z0-9._-]+@[a-zA-Z0-9._-]+\.[a-zA-Z0-9._-]+)/g,
            '<a href="mailto:$1">$1</a>'
        );
        
        // Handle line breaks
        processedContent = processedContent.replace(/\n/g, '<br>');
        
        bubble.innerHTML = processedContent;
        messageDiv.appendChild(bubble);
        chatMessages.appendChild(messageDiv);
    } else {
        messageDiv.appendChild(bubble);
        chatMessages.appendChild(messageDiv);

        // First handle code blocks (save them to restore later)
        let codeBlocks = [];
        let processedContent = content.replace(/```([\w:\/.-]+)?\n([\s\S]*?)```/g, (match, lang, code) => {
            codeBlocks.push({
                language: lang || 'code snippet',
                code: code.trim()
            });
            return `###CODEBLOCK${codeBlocks.length - 1}###`;
        });

        // Handle markdown formatting
        processedContent = processedContent
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\n\n/g, '</p><p>')
            .replace(/\n/g, '<br>');

        if (!processedContent.startsWith('<p>')) {
            processedContent = `<p>${processedContent}</p>`;
        }

        // Restore code blocks with syntax highlighting
        processedContent = processedContent.replace(/###CODEBLOCK(\d+)###/g, (match, index) => {
            const block = codeBlocks[index];
            return createCodeBlockHTML(block.language, block.code);
        });

        // Only apply typing effect for new messages, not loaded history
        if (!skipTyping) {
            await typeMessage(bubble, processedContent);
        } else {
            bubble.innerHTML = processedContent;
        }

        // Add image if present
        if (imageBase64) {
            const imgContainer = document.createElement('div');
            imgContainer.className = 'message-image';
            
            // Create image wrapper for better control
            const imgWrapper = document.createElement('div');
            imgWrapper.className = 'image-wrapper';
            imgWrapper.style.position = 'relative';
            imgWrapper.style.width = '400px'; // Set fixed width
            imgWrapper.style.margin = '10px 0';
            
            // Create image
            const img = document.createElement('img');
            img.src = `data:image/jpeg;base64,${imageBase64}`;
            img.alt = 'Generated Image';
            img.style.width = '100%';
            img.style.height = 'auto';
            img.style.borderRadius = '8px';
            img.style.cursor = 'pointer';
            
            // Add click to expand functionality
            img.onclick = () => {
                const modal = document.createElement('div');
                modal.style.position = 'fixed';
                modal.style.top = '0';
                modal.style.left = '0';
                modal.style.width = '100%';
                modal.style.height = '100%';
                modal.style.backgroundColor = 'rgba(0,0,0,0.9)';
                modal.style.display = 'flex';
                modal.style.justifyContent = 'center';
                modal.style.alignItems = 'center';
                modal.style.zIndex = '1000';
                
                const modalImg = document.createElement('img');
                modalImg.src = img.src;
                modalImg.style.maxWidth = '90%';
                modalImg.style.maxHeight = '90%';
                modalImg.style.objectFit = 'contain';
                
                modal.onclick = () => document.body.removeChild(modal);
                modal.appendChild(modalImg);
                document.body.appendChild(modal);
            };
            
            // Create controls container
            const controls = document.createElement('div');
            controls.className = 'image-controls';
            controls.style.position = 'absolute';
            controls.style.bottom = '10px';
            controls.style.right = '10px';
            controls.style.display = 'flex';
            controls.style.gap = '10px';
            controls.style.backgroundColor = 'rgba(0,0,0,0.5)';
            controls.style.padding = '5px';
            controls.style.borderRadius = '4px';
            
            // Download button
            const downloadBtn = document.createElement('button');
            downloadBtn.innerHTML = '💾';
            downloadBtn.title = 'Download Image';
            downloadBtn.className = 'image-control-btn';
            downloadBtn.onclick = (e) => {
                e.stopPropagation();
                const link = document.createElement('a');
                link.href = img.src;
                link.download = `generated-image-${Date.now()}.jpg`;
                link.click();
            };
            
            // Delete button
            const deleteBtn = document.createElement('button');
            deleteBtn.innerHTML = '🗑️';
            deleteBtn.title = 'Delete Image';
            deleteBtn.className = 'image-control-btn';
            deleteBtn.onclick = (e) => {
                e.stopPropagation();
                if (confirm('Are you sure you want to delete this image?')) {
                    imgContainer.remove();
                    // Update the stored chat to remove the image
                    let chats = JSON.parse(localStorage.getItem('chats') || '[]');
                    const currentChat = chats.find(chat => chat.id === currentChatId);
                    if (currentChat) {
                        currentChat.messages.forEach(msg => {
                            if (msg.imageData === imageBase64) {
                                msg.imageData = null;
                            }
                        });
                        localStorage.setItem('chats', JSON.stringify(chats));
                    }
                }
            };
            
            // Add buttons to controls
            controls.appendChild(downloadBtn);
            controls.appendChild(deleteBtn);
            
            // Assemble the image container
            imgWrapper.appendChild(img);
            imgWrapper.appendChild(controls);
            imgContainer.appendChild(imgWrapper);
            bubble.appendChild(imgContainer);
            
            // Add styles for the control buttons
            const style = document.createElement('style');
            style.textContent = `
                .image-control-btn {
                    background: none;
                    border: none;
                    color: white;
                    cursor: pointer;
                    font-size: 20px;
                    padding: 5px;
                    transition: transform 0.2s;
                }
                .image-control-btn:hover {
                    transform: scale(1.2);
                }
                .image-wrapper:hover .image-controls {
                    opacity: 1;
                }
                .image-controls {
                    opacity: 0;
                    transition: opacity 0.3s;
                }
            `;
            document.head.appendChild(style);
        }
    }

    chatMessages.scrollTop = chatMessages.scrollHeight;

    // Add syntax highlighting for code blocks
    if (!isUser) {
        Prism.highlightAll();
    }
}

// Function to create code block HTML
function createCodeBlockHTML(language, code) {
    return `
        <div class="code-block">
            <div class="code-header">
                <span class="code-language">${language}</span>
            </div>
            <div class="code-content">
                <pre><code class="language-${language.toLowerCase() || 'javascript'}">${escapeHtml(code)}</code></pre>
                <button class="code-copy-btn" onclick="copyCode(this)">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <path d="M8 17.929H6c-1.105 0-2 .912-2 2.036V5.036C4 3.912 4.895 3 6 3h8c1.105 0 2 .912 2 2.036v1.866m-6 .17h8c1.105 0 2-.911 2-2.035V9.107c0-1.124.895-2.036 2-2.036z" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                    Copy
                </button>
            </div>
        </div>
    `;
}

// Function to type message with animation
async function typeMessage(element, content) {
    let currentIndex = 0;
    let isInTag = false;
    let tagContent = '';
    let htmlContent = '';
    
    // Initial typing speed and acceleration settings with multiple phases
    const speedPhases = [
        { speed: 60, duration: 15 },  // Phase 1: Very slow start
        { speed: 30, duration: 25 },  // Phase 2: Medium speed
        { speed: 15, duration: 40 },  // Phase 3: Fast
        { speed: 5, duration: 60 },   // Phase 4: Very fast
        { speed: 2, duration: Infinity } // Final phase: Maximum speed
    ];
    
    let currentPhase = 0;
    let charactersTyped = 0;
    
    while (currentIndex < content.length) {
        const char = content[currentIndex];
        
        if (char === '<') {
            isInTag = true;
            tagContent = char;
            currentIndex++;
            continue;
        }
        
        if (isInTag) {
            tagContent += char;
            if (char === '>') {
                isInTag = false;
                htmlContent += tagContent;
                
                // If it's an opening tag for a code block, add the entire code block at once
                if (tagContent.includes('class="code-block"')) {
                    const codeBlockEnd = content.indexOf('</div></div>', currentIndex);
                    if (codeBlockEnd !== -1) {
                        const codeBlock = content.substring(currentIndex + 1, codeBlockEnd + 12);
                        htmlContent += codeBlock;
                        currentIndex = codeBlockEnd + 12;
                        element.innerHTML = htmlContent;
                        continue;
                    }
                }
            }
            currentIndex++;
            continue;
        }
        
        htmlContent += char;
        element.innerHTML = htmlContent;
        
        // Scroll to bottom while typing
        chatMessages.scrollTop = chatMessages.scrollHeight;
        
        // Update phase based on characters typed
        charactersTyped++;
        while (currentPhase < speedPhases.length - 1 && 
               charactersTyped >= speedPhases[currentPhase].duration) {
            currentPhase++;
        }
        
        currentIndex++;
        await new Promise(resolve => setTimeout(resolve, speedPhases[currentPhase].speed));
    }
}

// Helper function to escape HTML
function escapeHtml(unsafe) {
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Copy code function
function copyCode(button) {
    const codeBlock = button.closest('.code-block').querySelector('code');
    const text = codeBlock.textContent;
    
    navigator.clipboard.writeText(text).then(() => {
        const originalContent = button.innerHTML;
        button.innerHTML = `
            <svg stroke="currentColor" fill="none" stroke-width="2" viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round" height="1em" width="1em">
                <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
            Copied!
        `;
        button.classList.add('copied');
        
        setTimeout(() => {
            button.innerHTML = originalContent;
            button.classList.remove('copied');
        }, 2000);
    });
}

// Event Listeners
document.addEventListener('DOMContentLoaded', () => {
    loadChatHistory();
    
    // Load current chat if exists
    if (currentChatId) {
        loadChat(currentChatId);
    }

    // Add archive toggle listener
    const toggleArchivedBtn = document.getElementById('toggle-archived');
    if (toggleArchivedBtn) {
        toggleArchivedBtn.addEventListener('click', () => {
            isShowingArchived = !isShowingArchived;
            loadChatHistory();
        });
    }

    // New chat button
    document.getElementById('new-chat-button').addEventListener('click', () => {
        currentChatId = null;
        localStorage.removeItem('currentChatId');
        chatMessages.innerHTML = '';
    });

    // Send message on button click
    sendButton.addEventListener('click', sendMessage);

    // Send message on Enter (without shift)
    userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (!sendButton.disabled) sendMessage();
        }
    });

    // Enable/disable send button based on input
    userInput.addEventListener('input', function() {
        sendButton.disabled = !this.value.trim();
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 200) + 'px';
    });

    // Add clear conversations functionality
    const clearConversationsBtn = document.getElementById('clear-conversations');
    clearConversationsBtn.addEventListener('click', clearAllConversations);
    
    // Add theme toggle button listener
    document.getElementById('theme-toggle').addEventListener('click', toggleTheme);
    
    // Set initial theme
    document.body.classList.toggle('light-mode', !isDarkMode);

    // Add these functions for data export/import
    document.getElementById('export-chats').addEventListener('click', exportChats);
    document.getElementById('import-chats-btn').addEventListener('click', () => {
        document.getElementById('import-chats').click();
    });
    document.getElementById('import-chats').addEventListener('change', importChats);

    // Add null check before using forEach
    const elements = document.querySelectorAll('.your-selector');
    if (elements) {
        elements.forEach(element => {
            if (element) {  // Additional safety check
                element.addEventListener('click', function() {
                    // Your event handler code
                });
            }
        });
    }

    // Settings modal functionality
    const settingsBtn = document.getElementById('settings-btn');
    const settingsModal = document.getElementById('settings-modal');
    const closeSettings = document.getElementById('close-settings');
    const saveSettings = document.getElementById('save-settings');
    const apiKeyInput = document.getElementById('api-key');
    const hfApiKeyInput = document.getElementById('hf-api-key');
    const toggleApiVisibility = document.getElementById('toggle-api-visibility');
    const toggleHfApiVisibility = document.getElementById('toggle-hf-api-visibility');
    
    if (apiKey) {
        apiKeyInput.value = apiKey;
    }
    if (hfApiKey) {
        hfApiKeyInput.value = hfApiKey;
    }
    
    settingsBtn.addEventListener('click', () => {
        settingsModal.style.display = 'block';
    });
    
    closeSettings.addEventListener('click', () => {
        settingsModal.style.display = 'none';
    });
    
    // Add verify API key functions
    async function verifyGeminiKey(apiKey) {
        try {
            const response = await fetch('/verify-gemini-key', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ api_key: apiKey })
            });

            const data = await response.json();
            return {
                valid: data.valid,
                message: data.valid ? data.message : data.error
            };
        } catch (error) {
            console.error('Error verifying Gemini API key:', error);
            return {
                valid: false,
                message: 'Failed to verify API key: ' + error.message
            };
        }
    }

    // Update the settings event listener
    saveSettings.addEventListener('click', async function() {
        const newApiKey = apiKeyInput.value.trim();
        const newHfApiKey = hfApiKeyInput.value.trim();
        
        // Verify Gemini API key if provided
        if (newApiKey) {
            const verifyResult = await verifyGeminiKey(newApiKey);
            if (!verifyResult.valid) {
                showToast(verifyResult.message);
                return;
            }
        }

        // Verify Hugging Face API key if provided
        if (newHfApiKey) {
            const verifyResult = await verifyApiKey(newHfApiKey);
            if (!verifyResult.valid) {
                showToast(verifyResult.message);
                return;
            }
        }

        // Save keys if verification passed
        if (newApiKey) localStorage.setItem('apiKey', newApiKey);
        if (newHfApiKey) localStorage.setItem('hfApiKey', newHfApiKey);
        
        // Close modal and show success message
        settingsModal.style.display = 'none';
        showToast('Settings saved successfully!');
    });

    toggleApiVisibility.addEventListener('click', () => {
        const type = apiKeyInput.type;
        apiKeyInput.type = type === 'password' ? 'text' : 'password';
        toggleApiVisibility.querySelector('.show-key').style.display = type === 'password' ? 'none' : 'block';
        toggleApiVisibility.querySelector('.hide-key').style.display = type === 'password' ? 'block' : 'none';
    });
    
    toggleHfApiVisibility.addEventListener('click', () => {
        const type = hfApiKeyInput.type;
        hfApiKeyInput.type = type === 'password' ? 'text' : 'password';
        toggleHfApiVisibility.querySelector('.show-key').style.display = type === 'password' ? 'none' : 'block';
        toggleHfApiVisibility.querySelector('.hide-key').style.display = type === 'password' ? 'block' : 'none';
    });
    
    settingsModal.addEventListener('click', (e) => {
        if (e.target === settingsModal) {
            settingsModal.style.display = 'none';
        }
    });
}); 

// Add these functions at the top
function createHistoryItem(chat) {
    const historyItem = document.createElement('div');
    historyItem.className = 'history-item';
    historyItem.dataset.chatId = chat.id;
    
    historyItem.innerHTML = `
        <svg stroke="currentColor" fill="none" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"></path>
        </svg>
        <span class="chat-title">${chat.title || 'New Chat'}</span>
        <button class="chat-options-btn">
            <svg width="16" height="4" viewBox="0 0 16 4" fill="currentColor">
                <circle cx="2" cy="2" r="1.5"/>
                <circle cx="8" cy="2" r="1.5"/>
                <circle cx="14" cy="2" r="1.5"/>
            </svg>
        </button>
        <div class="chat-options-menu">
            <div class="chat-option edit-label">Edit label</div>
            <div class="chat-option archive">${chat.archived ? 'Unarchive chat' : 'Archive chat'}</div>
            <div class="chat-option delete">Delete chat</div>
        </div>
    `;

    // Add click event for loading chat
    historyItem.addEventListener('click', (e) => {
        if (!e.target.closest('.chat-options-btn') && !e.target.closest('.chat-options-menu')) {
            loadChat(chat.id);
        }
    });

    // Add options button functionality
    const optionsBtn = historyItem.querySelector('.chat-options-btn');
    const optionsMenu = historyItem.querySelector('.chat-options-menu');
    
    optionsBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        // Close all other menus first
        document.querySelectorAll('.chat-options-menu.active').forEach(menu => {
            if (menu !== optionsMenu) menu.classList.remove('active');
        });
        optionsMenu.classList.toggle('active');
    });

    // Add menu options functionality
    const editOption = historyItem.querySelector('.chat-option.edit-label');
    const archiveOption = historyItem.querySelector('.chat-option.archive');
    const deleteOption = historyItem.querySelector('.chat-option.delete');

    editOption.addEventListener('click', (e) => {
        e.stopPropagation();
        editChatLabel(chat.id);
        optionsMenu.classList.remove('active');
    });

    archiveOption.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleArchiveChat(chat.id);
        optionsMenu.classList.remove('active');
    });

    deleteOption.addEventListener('click', (e) => {
        e.stopPropagation();
        deleteChat(chat.id);
        optionsMenu.classList.remove('active');
    });

    // Close menu when clicking outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.chat-options-menu') && !e.target.closest('.chat-options-btn')) {
            optionsMenu.classList.remove('active');
        }
    });

    return historyItem;
}

function toggleArchiveChat(chatId) {
    const chats = JSON.parse(localStorage.getItem('chats') || '[]');
    const chat = chats.find(c => c.id === chatId);
    
    if (chat) {
        chat.archived = !chat.archived;
        localStorage.setItem('chats', JSON.stringify(chats));
        
        // If archiving current chat, clear the current view
        if (chat.id === currentChatId && chat.archived) {
            currentChatId = null;
            localStorage.removeItem('currentChatId');
            document.getElementById('chat-messages').innerHTML = '';
        }
        
        showToast(chat.archived ? 'Chat archived' : 'Chat unarchived');
        loadChatHistory();
    }
}

function editChatLabel(chatId) {
    const chats = JSON.parse(localStorage.getItem('chats') || '[]');
    const chat = chats.find(c => c.id === chatId);
    
    if (chat) {
        const editModal = document.createElement('div');
        editModal.className = 'modal';
        editModal.style.display = 'flex';
        
        editModal.innerHTML = `
            <div class="modal-content">
                <h3>Edit chat label</h3>
                <input type="text" class="edit-label-input" value="${chat.title}" 
                    placeholder="Enter new label" maxlength="30">
                <div class="modal-buttons">
                    <button class="modal-btn cancel">Cancel</button>
                    <button class="modal-btn save">Save</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(editModal);
        
        const input = editModal.querySelector('.edit-label-input');
        input.focus();
        input.select();
        
        editModal.querySelector('.cancel').addEventListener('click', () => {
            editModal.remove();
        });
        
        editModal.querySelector('.save').addEventListener('click', () => {
            const newLabel = input.value.trim();
            if (newLabel) {
                chat.title = newLabel;
                localStorage.setItem('chats', JSON.stringify(chats));
                loadChatHistory();
                showToast('Chat label updated');
            }
            editModal.remove();
        });
    }
}

function deleteChat(chatId) {
    const chats = JSON.parse(localStorage.getItem('chats') || '[]');
    const chatIndex = chats.findIndex(c => c.id === chatId);
    
    if (chatIndex !== -1) {
        chats.splice(chatIndex, 1);
        localStorage.setItem('chats', JSON.stringify(chats));
        showToast('Chat deleted');
        loadChatHistory();
    }
}

function showToast(message) {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => toast.classList.add('show'), 10);
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Add CSS for active state
const style = document.createElement('style');
style.textContent = `
    .history-item.active {
        background: rgba(255, 255, 255, 0.1);
    }
    
    .history-item {
        cursor: pointer;
        transition: background 0.2s;
    }
    
    .history-item:hover {
        background: rgba(255, 255, 255, 0.05);
    }
`;
document.head.appendChild(style); 

// Add typing indicator functions
function showTypingIndicator() {
    removeTypingIndicator(); // Remove any existing indicator first
    const typingDiv = document.createElement('div');
    typingDiv.className = 'message bot-message typing-indicator';
    typingDiv.innerHTML = `
        <div class="message-bubble">
            <div class="typing-indicator-content">
                <span class="thinking-text">thinking</span>
                <div class="typing-dots">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            </div>
        </div>
    `;
    chatMessages.appendChild(typingDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function removeTypingIndicator() {
    const typingIndicator = document.querySelector('.typing-indicator');
    if (typingIndicator) {
        typingIndicator.remove();
    }
}

// Add this function to handle theme switching
function toggleTheme() {
    isDarkMode = !isDarkMode;
    document.body.classList.toggle('light-mode', !isDarkMode);
    localStorage.setItem('darkMode', isDarkMode);
}

// Add these functions for data export/import
function exportChats() {
    const chats = localStorage.getItem('chats');
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(chats);
    const downloadAnchorNode = document.createElement('a');
    downloadAnchorNode.setAttribute("href", dataStr);
    downloadAnchorNode.setAttribute("download", "chat_history.json");
    document.body.appendChild(downloadAnchorNode);
    downloadAnchorNode.click();
    downloadAnchorNode.remove();
}

function importChats(event) {
    const file = event.target.files[0];
    const reader = new FileReader();
    
    reader.onload = function(e) {
        try {
            const chats = JSON.parse(e.target.result);
            localStorage.setItem('chats', JSON.stringify(chats));
            loadChatHistory();
            showToast('Chat history imported successfully');
        } catch (error) {
            showToast('Error importing chat history');
        }
    };
    
    reader.readAsText(file);
} 

// Function to clear all conversations
function clearAllConversations() {
    const modal = document.getElementById('confirm-modal');
    const confirmBtn = document.querySelector('#confirm-modal .confirm-btn');
    const cancelBtn = document.querySelector('#confirm-modal .cancel-btn');

    modal.style.display = 'block';

    confirmBtn.onclick = function() {
        // Clear all chats from localStorage
        localStorage.removeItem('chats');
        localStorage.removeItem('currentChatId');
        currentChatId = null;
        
        // Clear chat messages
        const chatMessages = document.getElementById('chat-messages');
        chatMessages.innerHTML = '';
        
        // Reload chat history (will be empty)
        loadChatHistory();
        
        modal.style.display = 'none';
        showToast('All conversations cleared');
    };

    cancelBtn.onclick = function() {
        modal.style.display = 'none';
    };

    // Close modal when clicking outside
    window.onclick = function(event) {
        if (event.target == modal) {
            modal.style.display = 'none';
        }
    };
}

async function verifyApiKey(apiKey) {
    try {
        // Basic format validation
        if (!apiKey || typeof apiKey !== 'string') {
            return {
                valid: false,
                message: "API key must be a non-empty string"
            };
        }

        // Clean the API key
        const cleanedKey = apiKey.trim().replace(/['"]/g, '');

        // Check if it starts with hf_
        if (!cleanedKey.startsWith('hf_')) {
            return {
                valid: false,
                message: "Invalid API key format. Key should start with 'hf_'"
            };
        }

        // Make a test request to verify the key
        const response = await fetch('/verify_api_key', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ api_key: cleanedKey })
        });

        const data = await response.json();
        
        if (!response.ok) {
            return {
                valid: false,
                message: data.message || "Failed to verify API key"
            };
        }

        return {
            valid: true,
            message: "API key verified successfully"
        };
    } catch (error) {
        console.error('Error verifying API key:', error);
        return {
            valid: false,
            message: "Error verifying API key. Please try again."
        };
    }
}
