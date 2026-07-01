// Frontend security module for examination locking

const ExamSecurity = {
    violationUrl: '/exam/violation',
    maxViolations: 3,

    // Disable mouse right clicks, copying, and pasting
    disableInteractions: function() {
        // Disable context menu
        document.addEventListener('contextmenu', e => {
            e.preventDefault();
            alert('Right click menu is disabled during the exam.');
        });

        // Disable copy
        document.addEventListener('copy', e => {
            e.preventDefault();
            alert('Copying text is disabled during the exam.');
        });

        // Disable cut
        document.addEventListener('cut', e => {
            e.preventDefault();
            alert('Cutting text is disabled during the exam.');
        });

        // Disable paste
        document.addEventListener('paste', e => {
            e.preventDefault();
            alert('Pasting text is disabled during the exam.');
        });
    },

    // Disable keys like F12, Ctrl+Shift+I, Ctrl+U, Ctrl+C, Ctrl+V
    disableKeyboardShortcuts: function() {
        document.addEventListener('keydown', e => {
            // F12 key
            if (e.key === 'F12' || e.keyCode === 123) {
                e.preventDefault();
                alert('Developer tools are disabled.');
                return false;
            }

            // Ctrl+Shift+I (Dev tools) or Ctrl+Shift+J (Console) or Ctrl+Shift+C (Inspect)
            if (e.ctrlKey && e.shiftKey && (e.key === 'I' || e.key === 'J' || e.key === 'C' || e.keyCode === 73 || e.keyCode === 74 || e.keyCode === 67)) {
                e.preventDefault();
                alert('Developer tools are disabled.');
                return false;
            }

            // Ctrl+U (View Source)
            if (e.ctrlKey && (e.key === 'u' || e.key === 'U' || e.keyCode === 85)) {
                e.preventDefault();
                alert('View page source is disabled.');
                return false;
            }

            // Ctrl+C, Ctrl+V, Ctrl+X
            if (e.ctrlKey && (e.key === 'c' || e.key === 'v' || e.key === 'x' || e.keyCode === 67 || e.keyCode === 86 || e.keyCode === 88)) {
                e.preventDefault();
                alert('Copy, Paste and Cut shortcuts are disabled.');
                return false;
            }
        });
    },

    // Request fullscreen on page start
    requestFullscreen: function(element) {
        if (element.requestFullscreen) {
            element.requestFullscreen();
        } else if (element.mozRequestFullScreen) { // Firefox
            element.mozRequestFullScreen();
        } else if (element.webkitRequestFullscreen) { // Chrome, Safari and Opera
            element.webkitRequestFullscreen();
        } else if (element.msRequestFullscreen) { // IE/Edge
            element.msRequestFullscreen();
        }
    },

    // Check if the page is currently in fullscreen mode
    isFullscreenActive: function() {
        return !!(document.fullscreenElement || 
                  document.mozFullScreenElement || 
                  document.webkitFullscreenElement || 
                  document.msFullscreenElement);
    },

    // Log a violation to the database via AJAX fetch
    reportViolation: function(reason) {
        console.warn('Violation triggered: ' + reason);
        
        const csrfInput = document.querySelector('input[name="csrf_token"]');
        const csrfToken = csrfInput ? csrfInput.value : '';
        
        fetch(this.violationUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': csrfToken
            }
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            if (data.auto_submitted) {
                alert('Exam terminated! You have exceeded the maximum allowed security violations.');
                window.location.reload(); // Reload triggers completion page redirection
            } else {
                alert(`Warning: ${reason} detected! This has been logged as a security violation. (Violation count: ${data.violation_count}/${this.maxViolations})`);
                // Attempt to re-engage fullscreen if they exited
                if (reason.includes('Fullscreen') && !this.isFullscreenActive()) {
                    this.promptReEnterFullscreen();
                }
            }
        })
        .catch(err => {
            console.error('Error logging violation:', err);
        });
    },

    // Setup tab-switching and window-blur listeners with a grace period
    setupTabSwitchDetection: function() {
        let isTabActive = true;

        // Establish a 1.5-second grace period for initial page rendering focus transitions
        setTimeout(() => {
            // Detect page visibility changes (Tab switches, minimizing window)
            document.addEventListener('visibilitychange', () => {
                if (document.hidden) {
                    isTabActive = false;
                    this.reportViolation('Leaving exam tab/switching windows');
                } else {
                    isTabActive = true;
                }
            });

            // Detect window blur (Focus moved to developer tools, OS popup, or secondary monitor window)
            window.addEventListener('blur', () => {
                if (isTabActive) {
                    this.reportViolation('Losing exam window focus');
                }
            });
        }, 1500);
    },

    // Setup fullscreen exit listener with a grace period
    setupFullscreenDetection: function() {
        let wasFullscreen = this.isFullscreenActive();

        setTimeout(() => {
            // Initialize/refresh fullscreen state after page load transitions
            wasFullscreen = this.isFullscreenActive();

            document.addEventListener('fullscreenchange', () => {
                const isFull = this.isFullscreenActive();
                if (!isFull && wasFullscreen) {
                    this.reportViolation('Exiting Fullscreen mode');
                    wasFullscreen = false;
                } else if (isFull) {
                    wasFullscreen = true;
                }
            });
        }, 1500);
    },

    // Prompt user to re-enter fullscreen
    promptReEnterFullscreen: function() {
        const overlay = document.createElement('div');
        overlay.id = 'fullscreen-blocker';
        overlay.style.position = 'fixed';
        overlay.style.top = '0';
        overlay.style.left = '0';
        overlay.style.width = '100vw';
        overlay.style.height = '100vh';
        overlay.style.backgroundColor = 'rgba(11, 15, 25, 0.95)';
        overlay.style.zIndex = '99999';
        overlay.style.display = 'flex';
        overlay.style.flexDirection = 'column';
        overlay.style.justifyContent = 'center';
        overlay.style.alignItems = 'center';
        overlay.style.color = '#ffffff';

        overlay.innerHTML = `
            <div style="text-align: center; padding: 2rem; max-width: 500px; border: 1px solid rgba(255,255,255,0.1); border-radius: 16px; background: rgba(255,255,255,0.02); backdrop-filter: blur(20px);">
                <h3 style="margin-bottom: 1rem; color: #ef4444;">Fullscreen Required</h3>
                <p style="color: #9ca3af; margin-bottom: 2rem;">The exam environment requires full screen mode to prevent cheating. Please click below to re-enter full screen.</p>
                <button id="re-enter-fs-btn" class="btn btn-danger btn-lg w-100" style="font-weight: 600; border-radius: 10px;">Re-enter Full Screen</button>
            </div>
        `;

        document.body.appendChild(overlay);

        const btn = document.getElementById('re-enter-fs-btn');
        btn.addEventListener('click', () => {
            this.requestFullscreen(document.documentElement);
            document.body.removeChild(overlay);
            // reset wasFullscreen in tracker
            setTimeout(() => { wasFullscreen = true; }, 100);
        });
    },

    // Initialize countdown timer
    initCountdownTimer: function(remainingSecs, displayElementId, formElementId) {
        let timeRemaining = remainingSecs;
        const display = document.getElementById(displayElementId);
        const form = document.getElementById(formElementId);

        if (!display) return;

        function updateTimerDisplay() {
            if (timeRemaining <= 0) {
                display.innerText = "00:00";
                clearInterval(timerInterval);
                alert("Exam time has expired! Submitting your exam.");
                if (form) {
                    form.submit();
                } else {
                    window.location.reload();
                }
                return;
            }

            const minutes = Math.floor(timeRemaining / 60);
            const seconds = timeRemaining % 60;

            const minStr = minutes < 10 ? '0' + minutes : minutes;
            const secStr = seconds < 10 ? '0' + seconds : seconds;

            display.innerText = `${minStr}:${secStr}`;
            timeRemaining--;
        }

        // Run immediately once
        updateTimerDisplay();

        const timerInterval = setInterval(updateTimerDisplay, 1000);
    },

    // Main entry point to initialize listeners for active exam
    initActiveExam: function(remainingSecs, displayId, formId) {
        this.disableInteractions();
        this.disableKeyboardShortcuts();
        this.setupFullscreenDetection();
        this.setupTabSwitchDetection();
        this.initCountdownTimer(remainingSecs, displayId, formId);
    }
};
