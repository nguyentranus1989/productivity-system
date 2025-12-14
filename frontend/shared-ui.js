/**
 * Shared UI Components - Loading Overlay & Custom Dialogs
 * Include this file in all HTML pages for consistent UX
 */

// ============================================
// LOADING OVERLAY
// ============================================
function initLoadingOverlay() {
    if (document.getElementById('loadingOverlay')) return; // Already exists

    const overlay = document.createElement('div');
    overlay.id = 'loadingOverlay';
    overlay.className = 'loading-overlay';
    overlay.innerHTML = `
        <div class="loading-spinner"></div>
        <div class="loading-text">Loading...</div>
    `;
    document.body.insertBefore(overlay, document.body.firstChild);
}

function showLoading(text = 'Loading...') {
    initLoadingOverlay();
    const overlay = document.getElementById('loadingOverlay');
    overlay.querySelector('.loading-text').textContent = text;
    overlay.classList.add('active');
}

function hideLoading() {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) overlay.classList.remove('active');
}

// ============================================
// CUSTOM DIALOG
// ============================================
let dialogResolve = null;

function initDialogOverlay() {
    if (document.getElementById('dialogOverlay')) return; // Already exists

    const overlay = document.createElement('div');
    overlay.id = 'dialogOverlay';
    overlay.className = 'dialog-overlay';
    overlay.innerHTML = `
        <div class="dialog-box">
            <div id="dialogIcon" class="dialog-icon warning">
                <i class="fas fa-exclamation-triangle"></i>
            </div>
            <div id="dialogTitle" class="dialog-title">Confirm Action</div>
            <div id="dialogMessage" class="dialog-message">Are you sure?</div>
            <div id="dialogButtons" class="dialog-buttons">
                <button class="dialog-btn cancel" onclick="resolveDialog(false)">Cancel</button>
                <button class="dialog-btn confirm" onclick="resolveDialog(true)">Confirm</button>
            </div>
        </div>
    `;
    document.body.insertBefore(overlay, document.body.firstChild);
}

function showDialog({ title, message, type = 'warning', confirmText = 'Confirm', cancelText = 'Cancel', showCancel = true, danger = false }) {
    initDialogOverlay();
    return new Promise((resolve) => {
        dialogResolve = resolve;
        const overlay = document.getElementById('dialogOverlay');
        const iconEl = document.getElementById('dialogIcon');
        const titleEl = document.getElementById('dialogTitle');
        const msgEl = document.getElementById('dialogMessage');
        const buttonsEl = document.getElementById('dialogButtons');

        // Set icon based on type
        const icons = {
            warning: 'fa-exclamation-triangle',
            danger: 'fa-trash-alt',
            info: 'fa-info-circle',
            question: 'fa-question-circle',
            success: 'fa-check-circle'
        };
        iconEl.className = `dialog-icon ${type}`;
        iconEl.innerHTML = `<i class="fas ${icons[type] || icons.warning}"></i>`;

        titleEl.textContent = title;
        msgEl.textContent = message;

        // Build buttons
        const confirmClass = danger ? 'dialog-btn danger' : 'dialog-btn confirm';
        if (showCancel) {
            buttonsEl.innerHTML = `
                <button class="dialog-btn cancel" onclick="resolveDialog(false)">${cancelText}</button>
                <button class="${confirmClass}" onclick="resolveDialog(true)">${confirmText}</button>
            `;
        } else {
            buttonsEl.innerHTML = `
                <button class="dialog-btn confirm" onclick="resolveDialog(true)">${confirmText}</button>
            `;
        }

        overlay.classList.add('active');
    });
}

function resolveDialog(result) {
    const overlay = document.getElementById('dialogOverlay');
    if (overlay) overlay.classList.remove('active');
    if (dialogResolve) {
        dialogResolve(result);
        dialogResolve = null;
    }
}

// Shorthand helpers
async function confirmDialog(title, message, options = {}) {
    return showDialog({ title, message, type: 'warning', ...options });
}

async function alertDialog(title, message, options = {}) {
    return showDialog({ title, message, type: 'info', showCancel: false, confirmText: 'OK', ...options });
}

// ============================================
// CSS INJECTION
// ============================================
function injectSharedStyles() {
    if (document.getElementById('shared-ui-styles')) return; // Already injected

    const style = document.createElement('style');
    style.id = 'shared-ui-styles';
    style.textContent = `
        /* Loading Overlay */
        .loading-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(15, 20, 25, 0.85);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            z-index: 9999;
            opacity: 0;
            visibility: hidden;
            transition: opacity 0.2s ease, visibility 0.2s ease;
        }
        .loading-overlay.active {
            opacity: 1;
            visibility: visible;
        }
        .loading-spinner {
            width: 48px;
            height: 48px;
            border: 4px solid rgba(255,255,255,0.1);
            border-top-color: #f59e0b;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }
        .loading-text {
            margin-top: 16px;
            color: #94a3b8;
            font-size: 0.9rem;
        }
        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        /* Custom Dialog Modal */
        .dialog-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(15, 20, 25, 0.9);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 10000;
            opacity: 0;
            visibility: hidden;
            transition: opacity 0.2s ease, visibility 0.2s ease;
        }
        .dialog-overlay.active {
            opacity: 1;
            visibility: visible;
        }
        .dialog-box {
            background: #1e252e;
            border: 1px solid rgba(245, 158, 11, 0.3);
            border-radius: 16px;
            padding: 32px;
            max-width: 420px;
            width: 90%;
            box-shadow: 0 8px 32px rgba(0,0,0,0.5);
            transform: scale(0.9);
            transition: transform 0.2s ease;
        }
        .dialog-overlay.active .dialog-box {
            transform: scale(1);
        }
        .dialog-icon {
            width: 48px;
            height: 48px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 16px;
            font-size: 1.5rem;
        }
        .dialog-icon.warning {
            background: rgba(245, 158, 11, 0.15);
            color: #f59e0b;
        }
        .dialog-icon.danger {
            background: rgba(239, 68, 68, 0.15);
            color: #ef4444;
        }
        .dialog-icon.info {
            background: rgba(59, 130, 246, 0.15);
            color: #3b82f6;
        }
        .dialog-icon.success {
            background: rgba(34, 197, 94, 0.15);
            color: #22c55e;
        }
        .dialog-title {
            font-size: 1.1rem;
            font-weight: 600;
            text-align: center;
            margin-bottom: 8px;
            color: #f8fafc;
        }
        .dialog-message {
            color: #94a3b8;
            text-align: center;
            white-space: pre-line;
            font-size: 0.9rem;
            line-height: 1.6;
            max-height: 300px;
            overflow-y: auto;
        }
        .dialog-buttons {
            display: flex;
            gap: 8px;
            margin-top: 24px;
            justify-content: center;
        }
        .dialog-btn {
            padding: 0.6rem 1.5rem;
            border-radius: 8px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
            border: none;
            font-size: 0.9rem;
        }
        .dialog-btn.cancel {
            background: #262d38;
            color: #94a3b8;
        }
        .dialog-btn.cancel:hover {
            background: #2d3748;
        }
        .dialog-btn.confirm {
            background: #f59e0b;
            color: #0f1419;
        }
        .dialog-btn.confirm:hover {
            background: #fbbf24;
        }
        .dialog-btn.danger {
            background: #ef4444;
            color: white;
        }
        .dialog-btn.danger:hover {
            filter: brightness(1.1);
        }
    `;
    document.head.appendChild(style);
}

// Auto-initialize on load
document.addEventListener('DOMContentLoaded', () => {
    injectSharedStyles();
});
