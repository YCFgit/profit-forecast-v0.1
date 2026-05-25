import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 60000,
})

// 数据导入
export const importFromSource = () => api.post('/import/from-source')

// 基线预估
export const getBaselines = () => api.get('/forecast/baselines')
export const getStoreBaseline = (code) => api.get(`/forecast/baselines/${code}`)

// 承压分配
export const allocateTargets = (totalTarget, withScenarios = true) =>
  api.post('/allocation/', { total_target: totalTarget, with_scenarios: withScenarios })
export const getScenarios = () => api.get('/allocation/scenarios')

// 利润测算
export const calculateProfit = (totalTarget) =>
  api.post('/profit/calculate', { total_target: totalTarget })
export const profitByRegion = () => api.get('/profit/drill-down/region')
export const profitByType = () => api.get('/profit/drill-down/type')

// 风险评估
export const assessRisk = (totalTarget) =>
  api.post('/risk/assess', { total_target: totalTarget })
export const runMonteCarlo = (totalTarget) =>
  api.post('/risk/monte-carlo', { total_target: totalTarget })

// 全流程
export const runPipeline = (totalTarget, adapter) =>
  api.post('/pipeline/run', { total_target: totalTarget, adapter })
export const pipelineHealth = () => api.get('/pipeline/health')

export default api
