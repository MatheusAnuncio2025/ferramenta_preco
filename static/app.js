/**
 * Garante que o container de toasts exista no DOM.
 */
function ensureToastContainer() {
    if (!document.getElementById('toast-container')) {
        const container = document.createElement('div');
        container.id = 'toast-container';
        document.body.appendChild(container);
    }
}

/**
 * Exibe uma notificação toast.
 * @param {string} message - A mensagem a ser exibida.
 * @param {('success'|'error')} type - O tipo de toast.
 */
function showToast(message, type = 'success') {
    ensureToastContainer();
    const container = document.getElementById('toast-container');
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span class="toast-message">${message}</span>`;
    
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.remove();
    }, 5000); // Remove o toast após 5 segundos
}


/**
 * Exibe um modal genérico na tela.
 * @param {object} config - Objeto de configuração do modal.
 * @param {string} config.title - O título do modal.
 * @param {string} config.bodyHtml - O conteúdo HTML do corpo do modal.
 * @param {Array<object>} config.buttons - Uma lista de objetos para os botões.
 */
function showAppModal({ title, bodyHtml, buttons }) {
    let modalOverlay = document.getElementById('app-modal');
    if (!modalOverlay) {
        modalOverlay = document.createElement('div');
        modalOverlay.id = 'app-modal';
        modalOverlay.className = 'modal-overlay';
        document.body.appendChild(modalOverlay);
    }

    modalOverlay.innerHTML = `
        <div class="modal-content">
            <h3 id="modal-title">${title}</h3>
            <div id="modal-body">${bodyHtml}</div>
            <div id="modal-buttons" class="modal-buttons"></div>
        </div>
    `;

    const modalButtonsContainer = modalOverlay.querySelector('#modal-buttons');
    buttons.forEach(btnInfo => {
        const button = document.createElement('button');
        button.textContent = btnInfo.text;
        button.className = `app-button modal-button ${btnInfo.class}`;
        button.onclick = () => {
            if (btnInfo.onClick) {
                const shouldClose = btnInfo.onClick(button);
                if (shouldClose !== false) {
                    closeAppModal();
                }
            } else {
                closeAppModal();
            }
        };
        modalButtonsContainer.appendChild(button);
    });

    requestAnimationFrame(() => {
        modalOverlay.classList.add('visible');
    });
}

/**
 * Fecha o modal.
 */
function closeAppModal() {
    const modalOverlay = document.getElementById('app-modal');
    if (modalOverlay) {
        modalOverlay.classList.remove('visible');
    }
}

/**
 * Verifica o status de autenticação do usuário e atualiza a navegação.
 * @returns {Promise<object|null>} - Retorna os dados do usuário se autenticado, senão null.
 */
async function checkAuthStatusAndUpdateNav() {
    try {
        const response = await fetch('/api/auth/status');
        const data = await response.json();
        
        const authContainer = document.getElementById('auth-container');
        const adminLink = document.getElementById('admin-link');
        const regrasLink = document.getElementById('regras-link');
        const campanhasLink = document.getElementById('campanhas-link');
        const historicoLink = document.getElementById('historico-link');
        const profilePic = document.getElementById('profile-pic');
        const userInfo = document.getElementById('user-info');
        const alertasLink = document.getElementById('alertas-link');


        if (data.authenticated) {
            if (window.location.pathname === '/' || window.location.pathname === '/login.html') {
                window.location.href = '/calculadora';
                return;
            }

            if (profilePic) profilePic.src = data.picture || `https://placehold.co/40x40/2ecc71/ffffff?text=${data.name ? data.name[0] : 'U'}`;
            if (userInfo) userInfo.textContent = `Olá, ${data.name.split(' ')[0]}!`;
            if (authContainer) authContainer.classList.remove('hidden');
            
            if (alertasLink) alertasLink.classList.remove('hidden');
            if (regrasLink) regrasLink.classList.remove('hidden');
            
            if (data.role === 'admin') {
                if (adminLink) adminLink.classList.remove('hidden');
                if (campanhasLink) campanhasLink.classList.remove('hidden');
            }
            
            if (data.pode_ver_historico) {
                if (historicoLink) historicoLink.classList.remove('hidden');
            }

            return data;
        } else {
            if (authContainer) authContainer.classList.add('hidden');

            const protectedPaths = ['/calculadora', '/lista', '/configuracoes', '/perfil', '/admin', '/regras', '/editar', '/pendente', '/historico', '/campanhas', '/alertas'];
            if (protectedPaths.some(path => window.location.pathname.startsWith(path))) {
                 window.location.href = '/';
            }
            return null;
        }
    } catch (error) {
        console.error('Falha ao verificar status de autenticação:', error);
        if (document.getElementById('auth-container')) {
            document.getElementById('auth-container').classList.add('hidden');
        }
        return null;
    }
}

/**
 * Adiciona o evento de clique para o botão de logout.
 */
function setupLogoutButton() {
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
        logoutBtn.onclick = () => {
            window.location.href = '/logout';
        };
    }
}