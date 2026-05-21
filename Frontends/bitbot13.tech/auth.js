/**
 * Authentication Management for BitBot13
 * Self-contained — no external dependencies
 *
 * NOTE on cross-site auth: all 3 Level 13 sites hit the same backend, so a JWT
 * issued on any site validates on any other. But localStorage is per-origin,
 * so each site must store its own token under a site-specific key. The user
 * still needs to log in once per site.
 */

class WallStBotsAuth {
  constructor(apiBaseUrl) {
    this.apiBaseUrl = apiBaseUrl;
    this.tokenKey = "bitbot13_jwt";
    this.userKey = "bitbot13_user";
    this.refreshTokenKey = "bitbot13_refresh_token";
  }

  async signup(email, password, fullName = null) {
    try {
      const response = await fetch(`${this.apiBaseUrl}/auth/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, full_name: fullName }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Signup failed");
      }

      const data = await response.json();

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

  async login(email, password) {
    try {
      const response = await fetch(`${this.apiBaseUrl}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || "Invalid email or password");
      }

      const data = await response.json();
      this.setToken(data.access_token);
      if (data.refresh_token) this.setRefreshToken(data.refresh_token);
      this.setUser({ email });

      return { success: true };
    } catch (error) {
      console.error("Login error:", error);
      throw error;
    }
  }

  logout() {
    localStorage.removeItem(this.tokenKey);
    localStorage.removeItem(this.userKey);
    localStorage.removeItem(this.refreshTokenKey);
  }

  getToken() { return localStorage.getItem(this.tokenKey); }
  setToken(token) { localStorage.setItem(this.tokenKey, token); }
  getRefreshToken() { return localStorage.getItem(this.refreshTokenKey); }
  setRefreshToken(token) { if (token) localStorage.setItem(this.refreshTokenKey, token); }
  getUser() {
    const u = localStorage.getItem(this.userKey);
    return u ? JSON.parse(u) : null;
  }
  setUser(user) { localStorage.setItem(this.userKey, JSON.stringify(user)); }
  isAuthenticated() { return !!this.getToken(); }
  getAuthHeader() {
    const token = this.getToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  isTokenExpired() {
    const token = this.getToken();
    if (!token) return true;
    try {
      const parts = token.split(".");
      if (parts.length !== 3) return true;
      const payload = JSON.parse(atob(parts[1]));
      return Date.now() >= payload.exp * 1000;
    } catch {
      return true;
    }
  }

  async refreshTokenIfNeeded() {
    if (!this.isTokenExpired()) return true;

    const refreshToken = this.getRefreshToken();
    if (!refreshToken) { this.logout(); return false; }

    try {
      const response = await fetch(`${this.apiBaseUrl}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!response.ok) { this.logout(); return false; }

      const data = await response.json();
      this.setToken(data.access_token);
      return true;
    } catch {
      this.logout();
      return false;
    }
  }
}

window.WallStBotsAuth = WallStBotsAuth;
