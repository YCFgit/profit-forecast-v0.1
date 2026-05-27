import { useState, useEffect } from 'react'
import {
  Card,
  Table,
  Input,
  Select,
  Tag,
  Space,
  Button,
  Statistic,
  Row,
  Col,
  Modal,
  Descriptions,
  Spin,
  message,
} from 'antd'
import {
  ShopOutlined,
  SearchOutlined,
  ReloadOutlined,
  EnvironmentOutlined,
  TeamOutlined,
} from '@ant-design/icons'
import { getStores, getStoreDetail, getStoreSummary } from '../api'

const { Search } = Input

const statusColors = {
  active: 'green',
  closed: 'red',
  renovating: 'orange',
}

const tierColors = {
  A: 'gold',
  B: 'blue',
  C: 'default',
  D: 'default',
}

export default function Stores() {
  const [stores, setStores] = useState([])
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(false)
  const [detailVisible, setDetailVisible] = useState(false)
  const [currentStore, setCurrentStore] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)

  // 筛选条件
  const [filters, setFilters] = useState({
    keyword: '',
    region: undefined,
    status: undefined,
    commercialTier: undefined,
  })

  // 加载门店列表
  const fetchStores = async () => {
    setLoading(true)
    try {
      const params = {}
      if (filters.keyword) params.keyword = filters.keyword
      if (filters.region) params.region = filters.region
      if (filters.status) params.status = filters.status
      if (filters.commercialTier) params.commercial_tier = filters.commercialTier

      const res = await getStores(params)
      setStores(res.data?.stores || [])
    } catch (err) {
      console.error('加载门店失败:', err)
      message.error('加载门店数据失败')
    } finally {
      setLoading(false)
    }
  }

  // 加载汇总数据
  const fetchSummary = async () => {
    try {
      const res = await getStoreSummary()
      setSummary(res.data)
    } catch (err) {
      console.error('加载汇总失败:', err)
    }
  }

  useEffect(() => {
    fetchStores()
    fetchSummary()
  }, [])

  // 查看门店详情
  const handleViewDetail = async (storeCode) => {
    setDetailLoading(true)
    setDetailVisible(true)
    try {
      const res = await getStoreDetail(storeCode)
      setCurrentStore(res.data)
    } catch (err) {
      message.error('加载门店详情失败')
      setDetailVisible(false)
    } finally {
      setDetailLoading(false)
    }
  }

  // 表格列定义
  const columns = [
    {
      title: '门店编码',
      dataIndex: 'store_code',
      key: 'store_code',
      width: 120,
      fixed: 'left',
      render: (text) => (
        <Button type="link" style={{ padding: 0, fontWeight: 500 }}>
          {text}
        </Button>
      ),
    },
    {
      title: '门店名称',
      dataIndex: 'store_name',
      key: 'store_name',
      width: 180,
      ellipsis: true,
    },
    {
      title: '区域',
      dataIndex: 'region',
      key: 'region',
      width: 100,
    },
    {
      title: '城市',
      dataIndex: 'city',
      key: 'city',
      width: 100,
    },
    {
      title: '类型',
      dataIndex: 'store_type',
      key: 'store_type',
      width: 100,
      render: (type) => {
        const typeMap = {
          direct: '直营',
          franchise: '加盟',
          virtual: '虚拟',
          temporary: '临时',
        }
        return typeMap[type] || type
      },
    },
    {
      title: '商圈',
      dataIndex: 'commercial_tier',
      key: 'commercial_tier',
      width: 80,
      render: (tier) => (
        <Tag color={tierColors[tier] || 'default'}>{tier}类</Tag>
      ),
    },
    {
      title: '面积(m²)',
      dataIndex: 'store_area',
      key: 'store_area',
      width: 100,
      render: (area) => area ? Number(area).toFixed(0) : '-',
      align: 'right',
    },
    {
      title: '人数',
      dataIndex: 'staff_count',
      key: 'staff_count',
      width: 80,
      align: 'right',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (status) => {
        const statusMap = {
          active: '营业中',
          closed: '已关闭',
          renovating: '装修中',
        }
        return (
          <Tag color={statusColors[status] || 'default'}>
            {statusMap[status] || status}
          </Tag>
        )
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      fixed: 'right',
      render: (_, record) => (
        <Button
          type="link"
          size="small"
          onClick={() => handleViewDetail(record.store_code)}
        >
          详情
        </Button>
      ),
    },
  ]

  // 提取筛选选项
  const regions = [...new Set(stores.map((s) => s.region).filter(Boolean))]
  const statuses = [...new Set(stores.map((s) => s.status).filter(Boolean))]
  const tiers = [...new Set(stores.map((s) => s.commercial_tier).filter(Boolean))]

  return (
    <div>
      {/* 汇总卡片 */}
      {summary && (
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={6}>
            <Card size="small">
              <Statistic
                title="门店总数"
                value={summary.total || 0}
                prefix={<ShopOutlined />}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card size="small">
              <Statistic
                title="营业中"
                value={summary.active || 0}
                valueStyle={{ color: '#52c41a' }}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card size="small">
              <Statistic
                title="总人数"
                value={summary.total_staff || 0}
                prefix={<TeamOutlined />}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card size="small">
              <Statistic
                title="总面积(m²)"
                value={summary.total_area || 0}
                precision={0}
                prefix={<EnvironmentOutlined />}
              />
            </Card>
          </Col>
        </Row>
      )}

      {/* 筛选条件 */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap>
          <Search
            placeholder="搜索门店编码/名称"
            allowClear
            style={{ width: 250 }}
            onSearch={(v) => {
              setFilters((prev) => ({ ...prev, keyword: v }))
              setTimeout(fetchStores, 0)
            }}
          />
          <Select
            placeholder="区域"
            allowClear
            style={{ width: 120 }}
            options={regions.map((r) => ({ label: r, value: r }))}
            onChange={(v) => setFilters((prev) => ({ ...prev, region: v }))}
          />
          <Select
            placeholder="状态"
            allowClear
            style={{ width: 120 }}
            options={statuses.map((s) => ({
              label: s === 'active' ? '营业中' : s === 'closed' ? '已关闭' : '装修中',
              value: s,
            }))}
            onChange={(v) => setFilters((prev) => ({ ...prev, status: v }))}
          />
          <Select
            placeholder="商圈等级"
            allowClear
            style={{ width: 120 }}
            options={tiers.map((t) => ({ label: `${t}类`, value: t }))}
            onChange={(v) => setFilters((prev) => ({ ...prev, commercialTier: v }))}
          />
          <Button icon={<ReloadOutlined />} onClick={fetchStores}>
            刷新
          </Button>
        </Space>
      </Card>

      {/* 门店列表 */}
      <Card
        title={
          <Space>
            <ShopOutlined />
            <span>门店列表</span>
            <Tag>{stores.length} 家</Tag>
          </Space>
        }
      >
        <Table
          columns={columns}
          dataSource={stores}
          rowKey="store_code"
          loading={loading}
          scroll={{ x: 1200 }}
          pagination={{
            pageSize: 20,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total) => `共 ${total} 家门店`,
          }}
          onRow={(record) => ({
            onClick: () => handleViewDetail(record.store_code),
            style: { cursor: 'pointer' },
          })}
        />
      </Card>

      {/* 门店详情弹窗 */}
      <Modal
        title={
          <Space>
            <ShopOutlined />
            <span>门店详情</span>
          </Space>
        }
        open={detailVisible}
        onCancel={() => {
          setDetailVisible(false)
          setCurrentStore(null)
        }}
        footer={null}
        width={700}
      >
        {detailLoading ? (
          <div style={{ textAlign: 'center', padding: 40 }}>
            <Spin size="large" />
          </div>
        ) : currentStore ? (
          <Descriptions bordered column={2} size="small">
            <Descriptions.Item label="门店编码">
              {currentStore.store_code}
            </Descriptions.Item>
            <Descriptions.Item label="门店名称">
              {currentStore.store_name}
            </Descriptions.Item>
            <Descriptions.Item label="区域">
              {currentStore.region}
            </Descriptions.Item>
            <Descriptions.Item label="城市">
              {currentStore.city}
            </Descriptions.Item>
            <Descriptions.Item label="类型">
              {currentStore.store_type === 'direct' ? '直营' : currentStore.store_type}
            </Descriptions.Item>
            <Descriptions.Item label="商圈">
              <Tag color={tierColors[currentStore.commercial_tier]}>
                {currentStore.commercial_tier}类
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="面积(m²)">
              {currentStore.store_area ? Number(currentStore.store_area).toFixed(0) : '-'}
            </Descriptions.Item>
            <Descriptions.Item label="人数">
              {currentStore.staff_count || '-'}
            </Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={statusColors[currentStore.status]}>
                {currentStore.status === 'active' ? '营业中' : currentStore.status}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="开业日期">
              {currentStore.opening_date || '-'}
            </Descriptions.Item>
            <Descriptions.Item label="省份">
              {currentStore.province || '-'}
            </Descriptions.Item>
            <Descriptions.Item label="是否虚拟店">
              {currentStore.is_virtual ? '是' : '否'}
            </Descriptions.Item>
          </Descriptions>
        ) : (
          <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>
            暂无数据
          </div>
        )}
      </Modal>
    </div>
  )
}
