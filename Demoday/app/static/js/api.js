// Configuration de base pour l'API
const API_BASE_URL = '/api/v1';

// Classe pour gérer les appels à l'API
class ApiService {
    constructor() {
        this.token = localStorage.getItem('auth_token');
        this.user = JSON.parse(localStorage.getItem('user') || 'null');
        this.updateProfileUI();
    }

    // Méthode pour configurer les headers
    getHeaders() {
        const headers = {
            'Content-Type': 'application/json'
        };
        
        if (this.token) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }
        
        return headers;
    }

    // Méthode pour gérer la connexion
    async login(email, password) {
        try {
            console.log('Tentative de connexion:', { email });  // Debug log
            
            const response = await fetch(`${API_BASE_URL}/auth/login`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify({ email, password })
            });
            
            const data = await response.json();
            console.log('Réponse du serveur:', data);  // Debug log

            if (response.ok && data.success) {
                this.user = data.data.user;
                this.token = data.data.token;
                localStorage.setItem('auth_token', this.token);
                localStorage.setItem('user', JSON.stringify(this.user));
                this.updateProfileUI();
                return { success: true, data: data.data };
            }
            
            return { 
                success: false, 
                error: data.message || 'Erreur de connexion'
            };
        } catch (error) {
            console.error('Erreur de connexion:', error);
            return { 
                success: false, 
                error: 'Erreur de communication avec le serveur'
            };
        }
    }

    // Méthode pour créer un compte utilisateur
    async register(username, email, password) {
        try {
            console.log('Tentative de création de compte:', { username, email });
            
            const response = await fetch(`${API_BASE_URL}/auth/register`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify({ username, email, password })
            });
            
            const data = await response.json();
            console.log('Réponse création de compte:', data);
            
            if (response.ok && data.success) {
                this.user = data.data.user;
                localStorage.setItem('user', JSON.stringify(this.user));
                this.updateProfileUI();
                return { success: true, data: data.data };
            }
            
            return { 
                success: false, 
                error: data.message || 'Erreur lors de la création du compte'
            };
        } catch (error) {
            console.error('Erreur création de compte:', error);
            return { success: false, error: 'Erreur de communication avec le serveur' };
        }
    }

    async deleteAccount() {
        if (!this.user || !this.user.id) {
            return { success: false, error: 'Aucun compte connecté' };
        }

        try {
            const response = await fetch(`${API_BASE_URL}/users/${this.user.id}`, {
                method: 'DELETE',
                headers: this.getHeaders()
            });
            const data = await response.json().catch(() => ({}));
            if (response.ok) {
                this.logout();
                return { success: true };
            }
            return {
                success: false,
                error: data.message || data.error || 'Impossible de supprimer le compte'
            };
        } catch (error) {
            console.error('Erreur suppression compte:', error);
            return { success: false, error: 'Erreur de communication avec le serveur' };
        }
    }

    logout() {
        this.token = null;
        this.user = null;
        localStorage.removeItem('auth_token');
        localStorage.removeItem('jwt_token');
        localStorage.removeItem('user');
        this.updateProfileUI();
    }

    updateProfileUI() {
        const userEmail = document.getElementById('user-email');
        const loginBtn = document.getElementById('login-btn');
        const logoutBtn = document.getElementById('logout-btn');
        const deleteBtn = document.getElementById('delete-btn');

        if (this.user) {
            if (userEmail) {
                userEmail.textContent = this.user.email;
                userEmail.style.display = 'block';
            }
            if (loginBtn) {
                loginBtn.style.display = 'none';
            }
            if (logoutBtn) {
                logoutBtn.style.display = 'block';
            }
            if (deleteBtn) {
                deleteBtn.style.display = 'block';
            }
        } else {
            if (userEmail) {
                userEmail.style.display = 'none';
            }
            if (loginBtn) {
                loginBtn.style.display = 'block';
            }
            if (logoutBtn) {
                logoutBtn.style.display = 'none';
            }
            if (deleteBtn) {
                deleteBtn.style.display = 'none';
            }
        }
    }

    // Gestion des produits
    async getProducts() {
        try {
            const response = await fetch(`${API_BASE_URL}/products`, {
                headers: this.getHeaders()
            });
            return await response.json();
        } catch (error) {
            console.error('Erreur lors de la récupération des produits:', error);
            return [];
        }
    }

    async createProduct(productData) {
        try {
            const response = await fetch(`${API_BASE_URL}/products`, {
                method: 'POST',
                headers: this.getHeaders(),
                body: JSON.stringify(productData)
            });
            return await response.json();
        } catch (error) {
            console.error('Erreur lors de la création du produit:', error);
            return null;
        }
    }

    async deleteProduct(productId) {
        try {
            const response = await fetch(`${API_BASE_URL}/products/${productId}`, {
                method: 'DELETE',
                headers: this.getHeaders()
            });
            return response.ok;
        } catch (error) {
            console.error('Erreur lors de la suppression du produit:', error);
            return false;
        }
    }

    // Gestion des catégories
    async getCategories() {
        try {
            const response = await fetch(`${API_BASE_URL}/categories`, {
                headers: this.getHeaders()
            });
            return await response.json();
        } catch (error) {
            console.error('Erreur lors de la récupération des catégories:', error);
            return [];
        }
    }

    async createCategory(categoryData) {
        try {
            const response = await fetch(`${API_BASE_URL}/categories`, {
                method: 'POST',
                headers: this.getHeaders(),
                body: JSON.stringify(categoryData)
            });
            return await response.json();
        } catch (error) {
            console.error('Erreur lors de la création de la catégorie:', error);
            return null;
        }
    }

    async deleteCategory(categoryId) {
        try {
            const response = await fetch(`${API_BASE_URL}/categories/${categoryId}`, {
                method: 'DELETE',
                headers: this.getHeaders()
            });
            return response.ok;
        } catch (error) {
            console.error('Erreur lors de la suppression de la catégorie:', error);
            return false;
        }
    }

    // Utilitaires
    isLoggedIn() {
        return !!this.user;
    }
}

window.FloraCart = {
    get() {
        try {
            const cart = JSON.parse(localStorage.getItem('cart') || '[]');
            return Array.isArray(cart) ? cart : [];
        } catch (error) {
            return [];
        }
    },
    save(cart) {
        localStorage.setItem('cart', JSON.stringify(cart));
    },
    itemKey(item) {
        if (!item) {
            return '';
        }
        if (item.type === 'subscription' || String(item.id || '').startsWith('subscription_')) {
            return `sub:${item.id || item.plan || item.name}`;
        }
        return `p:${item.id || item.product_id}`;
    },
    count(cart) {
        const items = cart || this.get();
        return items.reduce((sum, item) => sum + (Number(item.quantity) || 1), 0);
    },
    add(product) {
        const cart = this.get();
        const incomingQty = Number(product.quantity) || 1;
        if (product.type === 'subscription') {
            const withoutOld = cart.filter((item) => item.type !== 'subscription');
            withoutOld.push({ ...product, quantity: 1 });
            this.save(withoutOld);
            return withoutOld;
        }
        const key = this.itemKey(product);
        const existing = cart.find((item) => this.itemKey(item) === key);
        if (existing) {
            existing.quantity = (Number(existing.quantity) || 1) + incomingQty;
        } else {
            cart.push({ ...product, quantity: incomingQty });
        }
        this.save(cart);
        return cart;
    }
};

function updateCartCount() {
    const badge = document.getElementById('cart-count');
    if (!badge) {
        return;
    }
    const total = window.FloraCart.count();
    badge.textContent = String(total);
    badge.style.display = total > 0 ? 'inline-block' : 'none';
}

// Exporter une instance du service
const apiService = new ApiService();

// Redirection des boutons de connexion
document.addEventListener('DOMContentLoaded', () => {
    const loginButton = document.getElementById('loginButton');
    const registerButton = document.getElementById('registerButton');
    const forgotPasswordButton = document.getElementById('forgotPasswordButton');

    if (loginButton) {
        loginButton.addEventListener('click', () => {
            window.location.href = 'account.html';
        });
    }

    if (registerButton) {
        registerButton.addEventListener('click', () => {
            window.location.href = 'register.html';
        });
    }

    if (forgotPasswordButton) {
        forgotPasswordButton.addEventListener('click', () => {
            window.location.href = 'forgot-password.html';
        });
    }
});

// Initialisation au chargement de la page
document.addEventListener('DOMContentLoaded', () => {
    apiService.updateProfileUI();
    if (typeof updateCartCount === 'function') {
        updateCartCount();
    }
    
    // Gestionnaires d'événements pour le panel profil
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', () => {
            apiService.logout();
            window.location.href = 'accueil.html';
        });
    }

    const loginBtn = document.getElementById('login-btn');
    if (loginBtn) {
        loginBtn.addEventListener('click', () => {
            window.location.href = 'account.html';
        });
    }

    const deleteBtn = document.getElementById('delete-btn');
    if (deleteBtn) {
        deleteBtn.addEventListener('click', async () => {
            if (!confirm('Voulez-vous vraiment supprimer votre compte ? Cette action est irréversible.')) {
                return;
            }
            const result = await apiService.deleteAccount();
            if (result.success) {
                alert('Votre compte a été supprimé.');
                window.location.href = 'accueil.html';
            } else {
                alert(result.error || 'Impossible de supprimer le compte');
            }
        });
    }
});

// Filet de sécurité: garantit la gestion du panel et de la déconnexion
// même si certains templates ont des listeners en conflit.
document.addEventListener('click', (event) => {
    const profileLink = event.target.closest('#profile-link');
    if (profileLink) {
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();
        const panel = document.getElementById('profile-panel');
        if (panel) {
            panel.style.display = panel.style.display === 'block' ? 'none' : 'block';
        }
        return;
    }

    const logoutButton = event.target.closest('#logout-btn');
    if (!logoutButton) {
        const clickedInsidePanel = !!event.target.closest('#profile-panel');
        if (clickedInsidePanel) {
            return;
        }

        const panel = document.getElementById('profile-panel');
        if (!panel) {
            return;
        }
        panel.style.display = 'none';
        return;
    }

    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    apiService.logout();
    window.location.href = 'accueil.html';
}, true);
