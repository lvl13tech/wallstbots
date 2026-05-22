/**
 * API Client for Wall St. Bots Backend
 * Self-contained — no external dependencies
 */

class WallStBotsAPI {
  constructor(baseUrl, auth) {
    this.baseUrl = baseUrl;
    this.auth = auth;
  }

  async request(endpoint, options = {}) {
    await this.auth.refreshTokenIfNeeded();

    const url = `${this.baseUrl}${endpoint}`;
    const headers = {
      "Content-Type": "application/json",
      ...this.auth.getAuthHeader(),
      ...options.headers,
    };

    const response = await fetch(url, { ...options, headers });

    if (response.status === 401) {
      this.auth.logout();
      window.location.href = "/login.html";
      throw new Error("Session expired. Please log in again.");
    }

    if (!response.ok) {
      const error = await response.text();
      throw new Error(error || `API error: ${response.status}`);
    }

    if (response.status === 204) return null;

    return response.json();
  }

  // User
  async getUserProfile() { return this.request("/user/profile"); }
  async updateUserProfile(data) {
    return this.request("/user/profile", { method: "PUT", body: JSON.stringify(data) });
  }

  // Bots / Portfolios
  async getBots() { return this.request("/bots"); }
  async getBot(botId) { return this.request(`/bots/${botId}`); }
  async createBot(name, platform, description = null) {
    return this.request("/bots", {
      method: "POST",
      body: JSON.stringify({ name, platform, description }),
    });
  }
  async updateBot(botId, data) {
    return this.request(`/bots/${botId}`, { method: "PUT", body: JSON.stringify(data) });
  }
  async deleteBot(botId) {
    return this.request(`/bots/${botId}`, { method: "DELETE" });
  }

  // Holdings
  async getBotHoldings(botId) { return this.request(`/bots/${botId}/holdings`); }
  async addHolding(botId, symbol, weight, quantity = null, entryPrice = null) {
    return this.request(`/bots/${botId}/holdings`, {
      method: "POST",
      body: JSON.stringify({ symbol, weight, quantity, entry_price: entryPrice }),
    });
  }
  async updateHolding(botId, holdingId, data) {
    return this.request(`/bots/${botId}/holdings/${holdingId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  }
  async removeHolding(botId, holdingId) {
    return this.request(`/bots/${botId}/holdings/${holdingId}`, { method: "DELETE" });
  }

  // Performance
  async getBotPerformance(botId, days = 30) {
    return this.request(`/bots/${botId}/performance?days=${days}`);
  }
  async getBotLatestPerformance(botId) {
    return this.request(`/bots/${botId}/performance/latest`);
  }

  // Stock search (Polygon.io proxy)
  async searchStocks(query) {
    return this.request(`/stocks/search?q=${encodeURIComponent(query)}`);
  }

  // Subscriptions
  async getSubscription() { return this.request("/subscriptions/current"); }
  async validatePromoCode(code, botCount = 1) {
    return this.request("/promo-codes/validate", {
      method: "POST",
      body: JSON.stringify({ code, bot_count: botCount }),
    });
  }
  async calculateSubscriptionPrice(botCount, promoCode = null, referralCode = null) {
    return this.request("/subscriptions/calculate-price", {
      method: "POST",
      body: JSON.stringify({ bot_count: botCount, promo_code: promoCode, referral_code: referralCode }),
    });
  }

  // Public tracker (no auth)
  async getPublicTracker(dataType, platform = "lvl13") {
    const response = await fetch(`${this.baseUrl}/public/tracker/${dataType}?platform=${platform}`);
    if (!response.ok) throw new Error(`Tracker fetch failed: ${response.status}`);
    return response.json();
  }

  async healthCheck() {
    try {
      const r = await fetch(`${this.baseUrl}/health`);
      return r.ok;
    } catch { return false; }
  }
}

window.WallStBotsAPI = WallStBotsAPI;
