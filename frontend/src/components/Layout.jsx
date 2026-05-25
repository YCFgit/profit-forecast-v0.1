import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { Layout, Menu, Typography } from 'antd'
import {
  DashboardOutlined,
  SwapOutlined,
  DollarOutlined,
  AlertOutlined,
} from '@ant-design/icons'

const { Header, Content, Sider } = Layout
const { Title, Text } = Typography

const menuItems = [
  { key: '/', icon: <DashboardOutlined />, label: '利润总览' },
  { key: '/allocation', icon: <SwapOutlined />, label: '承压分配' },
  { key: '/profit', icon: <DollarOutlined />, label: '利润测算' },
  { key: '/risk', icon: <AlertOutlined />, label: '风险评估' },
]

const pageTitles = {
  '/': '利润总览',
  '/allocation': '承压分配',
  '/profit': '利润测算',
  '/risk': '风险评估',
}

export default function AppLayout() {
  const navigate = useNavigate()
  const location = useLocation()

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        breakpoint="lg"
        collapsedWidth="0"
        style={{
          background: 'linear-gradient(180deg, #0F172A 0%, #1E293B 100%)',
          boxShadow: '2px 0 8px rgba(0,0,0,0.15)',
        }}
      >
        <div style={{
          padding: '20px 16px',
          textAlign: 'center',
          borderBottom: '1px solid rgba(255,255,255,0.08)',
        }}>
          <Title level={4} style={{ color: '#fff', margin: 0, fontSize: 16, letterSpacing: 1 }}>
            利润测算系统
          </Title>
          <Text style={{ color: 'rgba(255,255,255,0.45)', fontSize: 11 }}>
            Profit Forecast
          </Text>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{ borderRight: 0, marginTop: 8 }}
        />
      </Sider>
      <Layout>
        <Header style={{
          padding: '0 24px',
          background: '#FFFFFF',
          borderBottom: '1px solid #E2E8F0',
          display: 'flex',
          alignItems: 'center',
          height: 56,
          boxShadow: '0 1px 2px rgba(0,0,0,0.03)',
        }}>
          <Title level={4} style={{ margin: 0, color: '#0F172A', fontWeight: 600 }}>
            {pageTitles[location.pathname] || '鞋服零售利润测算系统'}
          </Title>
        </Header>
        <Content style={{ margin: 20 }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}
