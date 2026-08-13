import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:5000",
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 30000,
});

const STORAGE_KEY = "riskoptimizer.auth";

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      try {
        const session = JSON.parse(raw);
        if (session.token) {
          config.headers.Authorization = `Bearer ${session.token}`;
        }
      } catch {
        localStorage.removeItem(STORAGE_KEY);
      }
    }
    return config;
  },
  (error) => Promise.reject(error),
);

// Track if a token refresh is in progress to avoid parallel refresh calls
let isRefreshing = false;
let failedQueue = [];

const processQueue = (error, token = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

// Response interceptor for error handling and 401 token refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then((token) => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            return api(originalRequest);
          })
          .catch((err) => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      const saved = localStorage.getItem(STORAGE_KEY);
      const session = saved ? JSON.parse(saved) : null;
      const refreshToken = session?.refresh_token || null;

      if (refreshToken) {
        try {
          const response = await api.post("/api/v1/auth/refresh", {
            refresh_token: refreshToken,
          });
          const newAccess =
            response.data?.data?.tokens?.access_token ||
            response.data?.data?.access_token;
          if (newAccess) {
            session.token = newAccess;
            localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
            api.defaults.headers.common.Authorization = `Bearer ${newAccess}`;
            processQueue(null, newAccess);
            originalRequest.headers.Authorization = `Bearer ${newAccess}`;
            return api(originalRequest);
          }
        } catch (refreshError) {
          processQueue(refreshError, null);
          localStorage.removeItem(STORAGE_KEY);
          window.location.href = "/login";
          return Promise.reject(refreshError);
        } finally {
          isRefreshing = false;
        }
      } else {
        isRefreshing = false;
        localStorage.removeItem(STORAGE_KEY);
        window.location.href = "/login";
      }
    }

    if (error.response) {
      const message =
        error.response.data?.error?.message ||
        error.response.data?.message ||
        "An error occurred";
      return Promise.reject(new Error(message));
    } else if (error.request) {
      return Promise.reject(
        new Error("Network error. Please check your connection."),
      );
    }
    return Promise.reject(error);
  },
);

// API endpoints
const endpoints = {
  // Auth
  login: "/api/v1/auth/login",
  register: "/api/v1/auth/register",
  logout: "/api/v1/auth/logout",
  refreshToken: "/api/v1/auth/refresh",

  // Portfolio
  getPortfolio: (address) => `/api/v1/portfolios/address/${address}`,
  getOnchainPortfolio: (address) =>
    `/api/v1/portfolios/address/${address}/onchain`,
  getPortfolioByUserId: (userId) => `/api/v1/portfolios/user/${userId}`,
  getAllPortfolios: "/api/v1/portfolios",
  createPortfolio: "/api/v1/portfolios",
  savePortfolio: "/api/v1/portfolios/save",
  updatePortfolio: (id) => `/api/v1/portfolios/${id}`,
  deletePortfolio: (id) => `/api/v1/portfolios/${id}`,

  // Risk analysis
  calculateVaR: "/api/v1/risk/var",
  calculateCVaR: "/api/v1/risk/cvar",
  calculateSharpeRatio: "/api/v1/risk/sharpe-ratio",
  calculateMaxDrawdown: "/api/v1/risk/max-drawdown",
  riskMetrics: "/api/v1/risk/portfolio-metrics",
  efficientFrontier: "/api/v1/risk/efficient-frontier",

  // Optimization (task controller)
  optimizePortfolio: "/api/v1/optimization/optimize",
  efficientFrontierOpt: "/api/v1/optimization/efficient-frontier",
  constraints: "/api/v1/optimization/constraints",

  // Market data
  marketData: "/api/v1/market/data",
  historicalPrices: "/api/v1/market/historical",
  realtimePrice: "/api/v1/market/realtime",
};

const apiService = {
  healthCheck: async () => {
    const response = await api.get("/health");
    return response.data;
  },

  auth: {
    login: async (credentials) => {
      const response = await api.post(endpoints.login, credentials);
      return response.data;
    },

    register: async (userData) => {
      const response = await api.post(endpoints.register, userData);
      return response.data;
    },

    logout: async () => {
      const response = await api.post(endpoints.logout);
      return response.data;
    },

    refresh: async (refreshToken) => {
      const response = await api.post(endpoints.refreshToken, {
        refresh_token: refreshToken,
      });
      return response.data;
    },
  },

  portfolio: {
    getByAddress: async (address) => {
      const response = await api.get(endpoints.getPortfolio(address));
      return response.data;
    },

    getOnchain: async (address) => {
      const response = await api.get(endpoints.getOnchainPortfolio(address));
      return response.data;
    },

    getByUserId: async (userId) => {
      const response = await api.get(endpoints.getPortfolioByUserId(userId));
      return response.data;
    },

    getAll: async (params = {}) => {
      const response = await api.get(endpoints.getAllPortfolios, { params });
      return response.data;
    },

    create: async (portfolioData) => {
      const response = await api.post(endpoints.createPortfolio, portfolioData);
      return response.data;
    },

    save: async (portfolioData) => {
      const response = await api.post(endpoints.savePortfolio, portfolioData);
      return response.data;
    },

    update: async (id, portfolioData) => {
      const response = await api.put(
        endpoints.updatePortfolio(id),
        portfolioData,
      );
      return response.data;
    },

    delete: async (id) => {
      const response = await api.delete(endpoints.deletePortfolio(id));
      return response.data;
    },
  },

  risk: {
    calculateVaR: async (params) => {
      const response = await api.post(endpoints.calculateVaR, params);
      return response.data;
    },

    calculateCVaR: async (params) => {
      const response = await api.post(endpoints.calculateCVaR, params);
      return response.data;
    },

    calculateSharpeRatio: async (params) => {
      const response = await api.post(endpoints.calculateSharpeRatio, params);
      return response.data;
    },

    calculateMaxDrawdown: async (params) => {
      const response = await api.post(endpoints.calculateMaxDrawdown, params);
      return response.data;
    },

    getMetrics: async (params) => {
      const response = await api.post(endpoints.riskMetrics, params);
      return response.data;
    },

    getEfficientFrontier: async (params) => {
      const response = await api.post(endpoints.efficientFrontier, params);
      return response.data;
    },
  },

  optimization: {
    optimize: async (params) => {
      const response = await api.post(endpoints.optimizePortfolio, params);
      return response.data;
    },

    efficientFrontier: async (params) => {
      const response = await api.post(endpoints.efficientFrontierOpt, params);
      return response.data;
    },

    getConstraints: async () => {
      const response = await api.get(endpoints.constraints);
      return response.data;
    },
  },

  market: {
    getData: async (symbols, params = {}) => {
      const response = await api.get(endpoints.marketData, {
        params: { symbols: symbols.join(","), ...params },
      });
      return response.data;
    },

    getHistoricalPrices: async (symbol, startDate, endDate) => {
      const response = await api.get(endpoints.historicalPrices, {
        params: { symbol, start_date: startDate, end_date: endDate },
      });
      return response.data;
    },

    getRealtimePrice: async (symbol) => {
      const response = await api.get(endpoints.realtimePrice, {
        params: { symbol },
      });
      return response.data;
    },
  },
};

export default apiService;
