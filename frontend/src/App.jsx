import { Routes, Route, Navigate } from 'react-router-dom'
import AppLayout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Allocation from './pages/Allocation'
import Profit from './pages/Profit'
import Risk from './pages/Risk'

function App() {
  return (
    <Routes>
      <Route path="/" element={<AppLayout />}>
        <Route index element={<Dashboard />} />
        <Route path="allocation" element={<Allocation />} />
        <Route path="profit" element={<Profit />} />
        <Route path="risk" element={<Risk />} />
      </Route>
    </Routes>
  )
}

export default App
