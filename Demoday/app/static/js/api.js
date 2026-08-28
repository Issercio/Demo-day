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
        deleteBtn.addEventListener('click', () => {
            alert('Suppression du compte (fonctionnalité à venir)');
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
