/** Cliente HTTP leve da Minha Financeira com token Bearer automático e tratamento de erros. */

const TOKEN_KEY = 'mf_access_token';

export function getStoredToken() {
  try {
    return localStorage.getItem(TOKEN_KEY) || '';
  } catch {
    return '';
  }
}

export function setStoredToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // ignore storage errors
  }
}

export async function apiRequest(path, options = {}) {
  const { method = 'GET', body, responseType = 'json' } = options;
  const headers = { ...(options.headers || {}) };
  const token = getStoredToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  let fetchBody;
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
    fetchBody = JSON.stringify(body);
  }

  const res = await fetch(path, { method, headers, body: fetchBody });

  if (res.status === 401 && !path.includes('/auth/login') && !path.includes('/auth/register')) {
    setStoredToken('');
    window.dispatchEvent(new CustomEvent('mf:unauthorized'));
  }

  if (!res.ok) {
    let message = `Erro ${res.status}`;
    try {
      const errData = await res.json();
      if (typeof errData?.detail === 'string') {
        message = errData.detail;
      } else if (Array.isArray(errData?.detail) && errData.detail[0]?.msg) {
        message = errData.detail[0].msg.replace(/^Value error,\s*/i, '');
      }
    } catch {
      // keep fallback message
    }
    const err = new Error(message);
    err.status = res.status;
    throw err;
  }

  if (responseType === 'blob') {
    const blob = await res.blob();
    const disp = res.headers.get('content-disposition') || '';
    const match = disp.match(/filename="?([^"]+)"?/i);
    return { blob, filename: match ? match[1] : 'minha_financeira_backup.zip' };
  }

  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  // Auth
  register: (payload) => apiRequest('/api/auth/register', { method: 'POST', body: payload }),
  login: (payload) => apiRequest('/api/auth/login', { method: 'POST', body: payload }),
  me: () => apiRequest('/api/auth/me'),
  updateMe: (payload) => apiRequest('/api/auth/me', { method: 'PUT', body: payload }),
  changePassword: (payload) => apiRequest('/api/auth/password', { method: 'PUT', body: payload }),

  // Painel
  painelResumo: (competencia) =>
    apiRequest(`/api/painel/resumo?competencia=${encodeURIComponent(competencia)}`),

  // Caixa
  listCaixa: (params = {}) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && String(v).trim() !== '') qs.set(k, String(v));
    });
    return apiRequest(`/api/caixa?${qs.toString()}`);
  },
  createCaixa: (payload) => apiRequest('/api/caixa', { method: 'POST', body: payload }),
  updateCaixa: (id, payload) => apiRequest(`/api/caixa/${id}`, { method: 'PUT', body: payload }),
  deleteCaixa: (id) => apiRequest(`/api/caixa/${id}`, { method: 'DELETE' }),

  // Contas a Vencer
  listContas: (competencia) =>
    apiRequest(`/api/contas?competencia=${encodeURIComponent(competencia)}`),
  createConta: (payload) => apiRequest('/api/contas', { method: 'POST', body: payload }),
  updateConta: (id, payload) => apiRequest(`/api/contas/${id}`, { method: 'PUT', body: payload }),
  deleteConta: (id) => apiRequest(`/api/contas/${id}`, { method: 'DELETE' }),
  pagarConta: (id, payload) =>
    apiRequest(`/api/contas/${id}/pagar`, { method: 'POST', body: payload }),
  estornarConta: (id, competencia) =>
    apiRequest(`/api/contas/${id}/pagamentos/${encodeURIComponent(competencia)}`, {
      method: 'DELETE',
    }),

  // Cartões
  listCartoes: (competencia) =>
    apiRequest(`/api/cartoes?competencia=${encodeURIComponent(competencia)}`),
  createCartao: (payload) => apiRequest('/api/cartoes', { method: 'POST', body: payload }),
  updateCartao: (id, payload) => apiRequest(`/api/cartoes/${id}`, { method: 'PUT', body: payload }),
  deleteCartao: (id) => apiRequest(`/api/cartoes/${id}`, { method: 'DELETE' }),
  createCartaoCompra: (cartaoId, payload) =>
    apiRequest(`/api/cartoes/${cartaoId}/compras`, { method: 'POST', body: payload }),
  deleteCartaoCompra: (cartaoId, compraId) =>
    apiRequest(`/api/cartoes/${cartaoId}/compras/${compraId}`, { method: 'DELETE' }),
  pagarCartao: (cartaoId, payload) =>
    apiRequest(`/api/cartoes/${cartaoId}/pagar`, { method: 'POST', body: payload }),
  estornarCartao: (cartaoId, competencia) =>
    apiRequest(`/api/cartoes/${cartaoId}/pagamentos/${encodeURIComponent(competencia)}`, {
      method: 'DELETE',
    }),

  // Módulos de Dívida estilo Cartão Virtual (Thiago, Seu Luiz, etc.)
  listModulos: (competencia) =>
    apiRequest(`/api/modulos-divida?competencia=${encodeURIComponent(competencia)}`),
  createModulo: (payload) => apiRequest('/api/modulos-divida', { method: 'POST', body: payload }),
  updateModulo: (id, payload) =>
    apiRequest(`/api/modulos-divida/${id}`, { method: 'PUT', body: payload }),
  deleteModulo: (id) => apiRequest(`/api/modulos-divida/${id}`, { method: 'DELETE' }),
  createModuloCompra: (moduloId, payload) =>
    apiRequest(`/api/modulos-divida/${moduloId}/compras`, { method: 'POST', body: payload }),
  deleteModuloCompra: (moduloId, compraId) =>
    apiRequest(`/api/modulos-divida/${moduloId}/compras/${compraId}`, { method: 'DELETE' }),
  pagarModulo: (moduloId, payload) =>
    apiRequest(`/api/modulos-divida/${moduloId}/pagar`, { method: 'POST', body: payload }),
  estornarModulo: (moduloId, competencia) =>
    apiRequest(`/api/modulos-divida/${moduloId}/pagamentos/${encodeURIComponent(competencia)}`, {
      method: 'DELETE',
    }),

  // Nuvem & Backup
  cloudStatus: () => apiRequest('/api/cloud/status'),
  cloudSyncNow: () => apiRequest('/api/cloud/vault/sync', { method: 'POST' }),
  exportBackupZip: () => apiRequest('/api/cloud/backup/export', { responseType: 'blob' }),
};
