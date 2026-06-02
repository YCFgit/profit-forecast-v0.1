import { Routes, Route, Navigate } from 'react-router-dom'
import AppLayout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Stores from './pages/Stores'
import Allocation from './pages/Allocation'
import Profit from './pages/Profit'
import Risk from './pages/Risk'
import Forecast from './pages/Forecast'
import { usePrefetch } from './hooks/usePrefetch'

function App() {
  // 应用启动时预热后端缓存
  usePrefetch()

  return (
    <Routes>
      <Route path="/" element={<AppLayout />}>
        <Route index element={<Dashboard />} />
        <Route path="stores" element={<Stores />} />
        <Route path="allocation" element={<Allocation />} />
        <Route path="profit" element={<Profit />} />
        <Route path="risk" element={<Risk />} />
        <Route path="forecast" element={<Forecast />} />
      </Route>
    </Routes>
  )
}

export default App
