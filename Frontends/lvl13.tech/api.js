/**
 * API Client for Wall St. Bots Backend
 * Handles all HTTP requests to the FastAPI backend
 */

class WallStBotsAPI {
  constructor(baseUrl, auth) {
    this.baseUrl = baseUrl;
    this.auth = auth; // WallStBotsAuth instance
  }

  /**
   * Make an HTTP request with auth headers
   */
  async request(endpoint, options = {}) {
    // Ensure token is fresh
    await this.auth.refreshTokenIfNeeded();

    const url = `${this.baseUrl}${endpoint}`;
    const headers = {
      "Content-Type": "application/json",
      ...this.auth.getAuthHeader(),
      ...options.headers,
    };

    const response = await fetch(url, {
      ...options,
      headers,
    });

    // Handle 401 (unauthorized) - token likely expired
    if (response.status === 401) {
      this.auth.logout();
      window.location.href = "/login.html";
      throw new Error("Session expired. Please log in again.");
    }

    if (!response.ok) {
      const error = await response.text();
      throw new Error(error || `API error: ${response.status}`);
    }

    // Some endpoints return empty responses
    if (response.status === 204) {
      return null;
    }

    return response.json();
  }

  // ========================================================================
  // USER ENDPOINTS
  // ========================================================================

  /**
   * Get current user's profile
   */
  async getUserProfile() {
    return this.request("/user/profile", { method: "GET" });
  }

  /**
   * Update user profile
   */
  async updateUserProfile(data) {
    return this.request("/user/profile", {
      method: "PUT",
      body: JSON.stringify(data),
    });
  }

  // ========================================================================
  // BOT ENDPOINTS
  // ========================================================================

  /**
   * List all bots for current user
   */
  async getBots() {
    return this.request("/bots", { method: "GET" });
  }

  /**
   * Get a specific bot with performance data
   */
  async getBot(botId) {
    return this.request(`/bots/${botId}`, { method: "GET" });
  }

  /**
   * Create a new bot
   */
  async createBot(name, platform, description = null) {
    return this.request("/bots", {
      method: "POST",
      body: JSON.stringify({
        name,
        platform,
        description,
      }),
    });
  }

  /**
   * Update a bot (name, description, etc.)
   */
  async updateBot(botId, data) {
    return this.request(`/bots/${botId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  }

  /**
   * Delete a bot (soft delete)
   */
  async deleteBot(botId) {
    return this.request(`/bots/${botId}`, { method: "DELETE" });
  }

  // ========================================================================
  // BOT HOLDINGS ENDPOINTS
  // ========================================================================

  /**
   * Get holdings for a bot
   */
  async getBotHoldings(botId) {
    return this.request(`/bots/${botId}/holdings`, { method: "GET" });
  }

  /**
   * Add a holding to a bot
   */
  async addHolding(botId, symbol, weight, quantity = null, entryPrice = null) {
    return this.request(`/bots/${botId}/holdings`, {
      method: "POST",
      body: JSON.stringify({
        symbol,
        weight,
        quantity,
        entry_price: entryPrice,
      }),
    });
  }

  /**
   * Update a holding
   */
  async updateHolding(botId, holdingId, data) {
    return this.request(`/bots/${botId}/holdings/${holdingId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  }

  /**
   * Remove a holding from a bot
   */
  async removeHolding(botId, holdingId) {
    return this.request(`/bots/${botId}/holdings/${holdingId}`, {
      method: "DELETE",
    });
  }

  // ========================================================================
  // PERFORMANCE ENDPOINTS
  // ========================================================================

  /**
   * Get performance history for a bot
   */
  async getBotPerformance(botId, days = 30) {
    return this.request(`/bots/${botId}/performance?days=${days}`, {
      method: "GET",
    });
  }

  /**
   * Get latest performance snapshot
   */
  async getBotLatestPerformance(botId) {
    return this.request(`/bots/${botId}/performance/latest`, {
      method: "GET",
    });
  }

  // ========================================================================
  // PROMO CODE ENDPOINTS
  // ========================================================================

  /**
   * Validate a promo code
   */
  async validatePromoCode(code, botCount = 1) {
    return this.request("/promo-codes/validate", {
      method: "POST",
      body: JSON.stringify({
        code,
        bot_count: botCount,
      }),
    });
  }

  // ========================================================================
  // SUBSCRIPTION & PAYMENT ENDPOINTS
  // ========================================================================

  /**
   * Calculate final price with discounts
   */
  async calculateSubscriptionPrice(botCount, promoCode = null, referralCode = null) {
    return this.request("/subscriptions/calculate-price", {
      method: "POST",
      body: JSON.stringify({
        bot_count: botCount,
        promo_code: promoCode,
        referral_code: referralCode,
      }),
    });
  }

  /**
   * Get user's subscription info
   */
  async getSubscription() {
    return this.request("/subscriptions/current", { method: "GET" });
  }

  // ========================================================================
  // REFERRAL ENDPOINTS
  // ========================================================================

  /**
   * Get user's referral code and stats
   */
  async getReferralStats() {
    return this.request("/user/referral-stats", { method: "GET" });
  }

  // ========================================================================
  // UTILITY
  // ========================================================================

  /**
   * Health check
   */
  async healthCheck() {
    try {
      const response = await fetch(`${this.baseUrl}/health`, {
        method: "GET",
      });
      return response.ok;
    } catch (error) {
      console.error("Health check failed:", error);
      return false;
    }
  }
}

// Export for use in HTML
window.WallStBotsAPI = WallStBotsAPI;
