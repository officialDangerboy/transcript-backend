let currentVideoId = null;
let transcriptData = null;
let plainTextData = null;

const youtubeUrlInput = document.getElementById('youtubeUrl');
const urlValidation = document.getElementById('urlValidation');
const getTranscriptBtn = document.getElementById('getTranscriptBtn');
const getSummaryBtn = document.getElementById('getSummaryBtn');
const languageSelect = document.getElementById('languageSelect');
const summaryLength = document.getElementById('summaryLength');
const timestampToggle = document.getElementById('timestampToggle');
const resultsSection = document.getElementById('resultsSection');
const darkModeToggle = document.getElementById('darkModeToggle');
const darkModeIcon = document.getElementById('darkModeIcon');

function validateYouTubeUrl(url) {
    const patterns = [
        /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})/,
        /^([a-zA-Z0-9_-]{11})$/
    ];
    
    for (const pattern of patterns) {
        if (pattern.test(url)) {
            return true;
        }
    }
    return false;
}

youtubeUrlInput.addEventListener('input', (e) => {
    const url = e.target.value.trim();
    if (url === '') {
        urlValidation.textContent = '';
        urlValidation.className = '';
        return;
    }
    
    if (validateYouTubeUrl(url)) {
        urlValidation.textContent = '✓ Valid YouTube URL';
        urlValidation.className = 'text-green-600 dark:text-green-400 font-semibold';
    } else {
        urlValidation.textContent = '✗ Invalid YouTube URL';
        urlValidation.className = 'text-red-600 dark:text-red-400 font-semibold';
    }
});

function showNotification(message, type = 'success') {
    const notification = document.getElementById('notification');
    notification.textContent = message;
    notification.className = `fixed top-4 right-4 px-6 py-4 rounded-lg shadow-lg text-white font-semibold z-50 notification-${type}`;
    notification.classList.remove('hidden');
    
    setTimeout(() => {
        notification.classList.add('hidden');
    }, 3000);
}

function setLoading(button, isLoading) {
    if (button === getTranscriptBtn) {
        document.getElementById('transcriptBtnText').classList.toggle('hidden', isLoading);
        document.getElementById('transcriptLoader').classList.toggle('hidden', !isLoading);
        button.disabled = isLoading;
    } else {
        document.getElementById('summaryBtnText').classList.toggle('hidden', isLoading);
        document.getElementById('summaryLoader').classList.toggle('hidden', !isLoading);
        button.disabled = isLoading;
    }
}

getTranscriptBtn.addEventListener('click', async () => {
    const url = youtubeUrlInput.value.trim();
    
    if (!validateYouTubeUrl(url)) {
        showNotification('Please enter a valid YouTube URL', 'error');
        return;
    }
    
    setLoading(getTranscriptBtn, true);
    
    try {
        await fetchLanguages(url);
        
        const response = await fetch('/api/transcript', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                url: url,
                language: languageSelect.value,
                include_timestamps: timestampToggle.checked
            })
        });
        
        const data = await response.json();
        
        if (!data.success) {
            showNotification(data.error, 'error');
            return;
        }
        
        transcriptData = data.transcript;
        plainTextData = data.plain_text;
        
        displayVideoInfo(data.video_info);
        displayTranscript(data.transcript, data.plain_text, data.word_count, data.char_count);
        
        resultsSection.classList.remove('hidden');
        resultsSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        
        showNotification('Transcript fetched successfully!', 'success');
    } catch (error) {
        showNotification('Unable to connect. Please check your internet', 'error');
    } finally {
        setLoading(getTranscriptBtn, false);
    }
});

getSummaryBtn.addEventListener('click', async () => {
    const url = youtubeUrlInput.value.trim();
    
    if (!validateYouTubeUrl(url)) {
        showNotification('Please enter a valid YouTube URL', 'error');
        return;
    }
    
    setLoading(getSummaryBtn, true);
    
    try {
        const response = await fetch('/api/summary', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                url: url,
                language: languageSelect.value,
                length: summaryLength.value
            })
        });
        
        const data = await response.json();
        
        if (!data.success) {
            showNotification(data.error, 'error');
            return;
        }
        
        displayVideoInfo(data.video_info);
        displaySummary(data.summary, data.word_count, data.reading_time, data.processing_time);
        
        resultsSection.classList.remove('hidden');
        switchTab('summary');
        resultsSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        
        showNotification('Summary generated successfully!', 'success');
    } catch (error) {
        showNotification('Unable to connect. Please check your internet', 'error');
    } finally {
        setLoading(getSummaryBtn, false);
    }
});

async function fetchLanguages(url) {
    try {
        const response = await fetch('/api/languages', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url: url })
        });
        
        const data = await response.json();
        
        if (data.success && data.languages) {
            languageSelect.innerHTML = '';
            data.languages.forEach(lang => {
                const option = document.createElement('option');
                option.value = lang.code;
                option.textContent = `${lang.name} ${lang.is_generated ? '(Auto)' : ''}`;
                languageSelect.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Error fetching languages:', error);
    }
}

function displayVideoInfo(videoInfo) {
    if (!videoInfo || !videoInfo.success) return;
    
    document.getElementById('videoThumbnail').src = videoInfo.thumbnail;
    document.getElementById('videoTitle').textContent = videoInfo.title;
    document.getElementById('videoId').textContent = `Video ID: ${videoInfo.video_id}`;
}

function displayTranscript(transcript, plainText, wordCount, charCount) {
    document.getElementById('transcriptText').textContent = transcript;
    document.getElementById('plaintextText').textContent = plainText;
    document.getElementById('transcriptStats').textContent = `${wordCount} words, ${charCount} characters`;
    document.getElementById('plaintextStats').textContent = `${wordCount} words, ${charCount} characters`;
}

function displaySummary(summary, wordCount, readingTime, processingTime) {
    document.getElementById('summaryText').textContent = summary;
    document.getElementById('summaryStats').textContent = `${wordCount} words, ${readingTime} min read, Generated in ${processingTime}s`;
}

timestampToggle.addEventListener('change', async () => {
    if (transcriptData) {
        const url = youtubeUrlInput.value.trim();
        setLoading(getTranscriptBtn, true);
        
        try {
            const response = await fetch('/api/transcript', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    url: url,
                    language: languageSelect.value,
                    include_timestamps: timestampToggle.checked
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                document.getElementById('transcriptText').textContent = data.transcript;
            }
        } catch (error) {
            console.error('Error updating transcript:', error);
        } finally {
            setLoading(getTranscriptBtn, false);
        }
    }
});

const tabButtons = document.querySelectorAll('.tab-btn');
tabButtons.forEach(button => {
    button.addEventListener('click', () => {
        const tabName = button.dataset.tab;
        switchTab(tabName);
    });
});

function switchTab(tabName) {
    tabButtons.forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(content => content.classList.add('hidden'));
    
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
    document.getElementById(`tab-${tabName}`).classList.remove('hidden');
}

function copyToClipboard(elementId) {
    const text = document.getElementById(elementId).textContent;
    navigator.clipboard.writeText(text).then(() => {
        showNotification('Copied to clipboard!', 'success');
    }).catch(() => {
        showNotification('Failed to copy', 'error');
    });
}

function downloadText(elementId, filename) {
    const text = document.getElementById(elementId).textContent;
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${filename}-${Date.now()}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showNotification('Downloaded successfully!', 'success');
}

if (localStorage.getItem('darkMode') === 'enabled') {
    document.documentElement.classList.add('dark');
    darkModeIcon.textContent = '☀️';
}

darkModeToggle.addEventListener('click', () => {
    document.documentElement.classList.toggle('dark');
    
    if (document.documentElement.classList.contains('dark')) {
        localStorage.setItem('darkMode', 'enabled');
        darkModeIcon.textContent = '☀️';
    } else {
        localStorage.setItem('darkMode', 'disabled');
        darkModeIcon.textContent = '🌙';
    }
});
