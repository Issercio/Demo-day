// Configuration de base pour l'API
const API_BASE_URL = 'http://localhost:5000/api/v1';

// Classe pour gérer les appels à l'API
class ApiService {
    constructor() {
        this.token = localStorage.getItem('auth_token');
        this.user = JSON.parse(localStorage.getItem('user') || 'null');
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
                localStorage.setItem('user', JSON.stringify(this.user));
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
    async register(userData) {
        try {
            const response = await fetch(`${API_BASE_URL}/auth/register`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(userData)
            });
            
            const data = await response.json();
            return { success: response.ok, data };
        } catch (error) {
            console.error('Erreur lors de l\'inscription:', error);
            return { success: false, error: 'Erreur lors de l\'inscription' };
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
        return !!this.token;
    }

    isAdmin() {
        return this.user && this.user.is_admin;
    }

    logout() {
        this.user = null;
        localStorage.removeItem('user');
    }

    getUser() {
        return JSON.parse(localStorage.getItem('user'));
    }

    async deleteAccount() {
        try {
            const response = await fetch(`${API_BASE_URL}/users/me`, {
                method: 'DELETE',
                headers: this.getHeaders()
            });
            
            if (response.ok) {
                this.logout();
                return { success: true };
            }
            return { success: false, error: 'Erreur lors de la suppression du compte' };
        } catch (error) {
            console.error('Erreur:', error);
            return { success: false, error: 'Erreur de communication avec le serveur' };
        }
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
