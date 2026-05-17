/**
 * Authentication Management for Wall St. Bots
 * Handles login, signup, JWT token management, and session persistence
 */

class WallStBotsAuth {
  constructor(apiBaseUrl) {
    this.apiBaseUrl = apiBaseUrl;
    this.tokenKey = "wallstbots_jwt";
    this.userKey = "wallstbots_user";
    this.refreshTokenKey = "wallstbots_refresh_token";
  }

  /**
   * Sign up a new user
   */
  async signup(email, password, fullName = null) {
    try {
      const response = await fetch(`${this.apiBaseUrl}/auth/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          password,
          full_name: fullName,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Signup failed");
      }

      const data = await response.json();

      // Store JWT
      if (data.access_token) {
        this.setToken(data.access_token);
        this.setRefreshToken(data.refresh_token);
        this.setUser({ email, full_name: fullName });
      }

      return { success: true, message: "Signup successful. Check your email to confirm." };
    } catch (error) {
      console.error("Signup error:", error);
      throw error;
    }
  }

  /**
   * Log in with email and password
   */
  async login(email, password) {
    try {
      const response = await fetch(`${this.apiBaseUrl}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      if (!response.ok) {
        throw new Error("Invalid email or password");
      }

      const data = await response.json();

      // Store JWT and user info
      this.setToken(data.access_token);
      if (data.refresh_token) {
        this.setRefreshToken(data.refresh_token);
      }
      this.setUser({ email });

      return { success: true };
    } catch (error) {
      console.error("Login error:", error);
      throw error;
    }
  }

  /**
   * Log out the current user
   */
  logout() {
    localStorage.removeItem(this.tokenKey);
    localStorage.removeItem(this.userKey);
    localStorage.removeItem(this.refreshTokenKey);
  }

  /**
   * Get the current JWT token
   */
  getToken() {
    return localStorage.getItem(this.tokenKey);
  }

  /**
   * Set the JWT token
   */
  setToken(token) {
    localStorage.setItem(this.tokenKey, token);
  }

  /**
   * Get the refresh token
   */
  getRefreshToken() {
    return localStorage.getItem(this.refreshTokenKey);
  }

  /**
   * Set the refresh token
   */
  setRefreshToken(token) {
    if (token) {
      localStorage.setItem(this.refreshTokenKey, token);
    }
  }

  /**
   * Get stored user info
   */
  getUser() {
    const user = localStorage.getItem(this.userKey);
    return user ? JSON.parse(user) : null;
  }

  /**
   * Set user info
   */
  setUser(user) {
    localStorage.setItem(this.userKey, JSON.stringify(user));
  }

  /**
   * Check if user is authenticated
   */
  isAuthenticated() {
    return !!this.getToken();
  }

  /**
   * Get Authorization header for API calls
   */
  getAuthHeader() {
    const token = this.getToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  /**
   * Decode JWT to check expiration
   */
  isTokenExpired() {
    const token = this.getToken();
    if (!token) return true;

    try {
      const parts = token.split(".");
      if (parts.length !== 3) return true;

      const payload = JSON.parse(atob(parts[1]));
      const expirationTime = payload.exp * 1000; // Convert to milliseconds

      return Date.now() >= expirationTime;
    } catch (error) {
      console.error("Token decode error:", error);
      return true;
    }
  }

  /**
   * Refresh JWT token if expired
   */
  async refreshTokenIfNeeded() {
    if (!this.isTokenExpired()) {
      return true;
    }

    const refreshToken = this.getRefreshToken();
    if (!refreshToken) {
      // No refresh token available, user must re-authenticate
      this.logout();
      return false;
    }

    try {
      const response = await fetch(`${this.apiBaseUrl}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!response.ok) {
        this.logout();
        return false;
      }

      const data = await response.json();
      this.setToken(data.access_token);

      return true;
    } catch (error) {
      console.error("Token refresh error:", error);
      this.logout();
      return false;
    }
  }
}

// Export for use in HTML
window.WallStBotsAuth = WallStBotsAuth;
