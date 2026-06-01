import { useState } from 'react'
import { Card, Row, Col, Statistic, Button, InputNumber, Spin, message, Tag, Table, Tooltip } from 'antd'
import {
  DollarOutlined,
  ShopOutlined,
  TrophyOutlined,
  AlertOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import { runPipeline } from '../api'
import { colors, chartColors } from '../theme'

export default function Dashboard() {
  const [loading, setLoading] = useState(false)
  const [target, setTarget] = useState(10000000)
  const [result, setResult] = useState(null)

  const handleRun = async () => {
    setLoading(true)
    try {
      const res = await runPipeline(target, 'mysql')
      setResult(res.data)
      message.success('测算完成')
    } catch (err) {
      message.error('测算失败: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const riskMap = {
    low:      { color: 'green', label: '低风险', desc: '目标可达，承压均匀' },
    medium:   { color: 'orange', label: '中风险', desc: '需关注个别门店' },
    high:     { color: 'red', label: '高风险', desc: '目标激进，需调整' },
    critical: { color: 'red', label: '极高风险', desc: '建议重新制定方案' },
  }
  const getRiskColor = (level) => riskMap[level]?.color || 'default'

  const getAllocationPieOption = () => {
    if (!result) return {}
    const data = result.allocation_detail.slice(0, 10).map(d => ({
      name: d.store_code,
      value: d.target,
    }))
    return {
      title: { text: '门店目标分配 (Top 10)', left: 'center', textStyle: { fontSize: 14, color: colors.text } },
      tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
      color: chartColors,
      series: [{
        type: 'pie',
        radius: ['40%', '70%'],
        data,
        label: { formatter: '{b}\n{d}%', fontSize: 11 },
        emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.15)' } },
      }],
    }
  }

  const getGrowthBarOption = () => {
    if (!result) return {}
    const sorted = [...result.allocation_detail].sort((a, b) => {
      return parseFloat(b.growth_rate) - parseFloat(a.growth_rate)
    }).slice(0, 15)
    return {
      title: { text: '门店增长率排行 (Top 15)', left: 'center', textStyle: { fontSize: 14, color: colors.text } },
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'category',
        data: sorted.map(d => d.store_code),
        axisLabel: { rotate: 45, fontSize: 11 },
      },
      yAxis: { type: 'value', axisLabel: { formatter: '{value}%' } },
      grid: { top: 40, bottom: 60, left: 50, right: 20 },
      series: [{
        type: 'bar',
        data: sorted.map(d => parseFloat(d.growth_rate)),
        itemStyle: {
          color: (params) => {
            const v = params.value
            if (v > 25) return colors.danger
            if (v > 15) return colors.warning
            return colors.success
          },
          borderRadius: [4, 4, 0, 0],
        },
        barMaxWidth: 32,
      }],
    }
  }

  return (
    <div>
      <Card
        style={{ marginBottom: 16, borderTop: `3px solid ${colors.primary}` }}
      >
        <Row gutter={16} align="middle">
          <Col>
            <span style={{ color: colors.textSecondary, fontWeight: 500 }}>总利润目标: </span>
            <InputNumber
              value={target}
              onChange={setTarget}
              formatter={v => `¥ ${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
              parser={v => v.replace(/¥\s?|(,*)/g, '')}
              style={{ width: 200 }}
              step={1000000}
            />
          </Col>
          <Col>
            <Button
              type="primary"
              icon={<ThunderboltOutlined />}
              onClick={handleRun}
              loading={loading}
              size="large"
            >
              一键测算
            </Button>
          </Col>
        </Row>
      </Card>

      {loading && <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />}

      {result && !loading && (
        <>
          {/* 关键指标卡片 */}
          <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
            <Col xs={24} sm={12} md={6} lg={4}>
              <Card hoverable style={{ borderLeft: `3px solid ${colors.primary}` }}>
                <Statistic title="总目标" value={result.summary['总目标']} prefix="¥" precision={0} />
              </Card>
            </Col>
            <Col xs={24} sm={12} md={6} lg={4}>
              <Card hoverable style={{ borderLeft: `3px solid ${result.summary['净利润'] > 0 ? colors.success : colors.danger}` }}>
                <Statistic
                  title="净利润"
                  value={result.summary['净利润']}
                  prefix="¥"
                  precision={0}
                  valueStyle={{ color: result.summary['净利润'] > 0 ? colors.success : colors.danger }}
                />
              </Card>
            </Col>
            <Col xs={24} sm={12} md={6} lg={3}>
              <Card hoverable style={{ borderLeft: `3px solid ${colors.primaryLight}` }}>
                <Statistic title="净利率" value={result.summary['净利率']} valueStyle={{ color: colors.primaryLight }} />
              </Card>
            </Col>
            <Col xs={24} sm={12} md={6} lg={3}>
              <Card hoverable style={{ borderLeft: `3px solid ${colors.accent}` }}>
                <Statistic title="门店数" value={result.summary['门店数']} prefix={<ShopOutlined style={{ color: colors.accent }} />} />
              </Card>
            </Col>
            <Col xs={24} sm={12} md={6} lg={3}>
              <Card hoverable style={{ borderLeft: `3px solid ${colors.success}` }}>
                <Statistic title="盈利门店" value={result.summary['盈利门店']} prefix={<TrophyOutlined />} valueStyle={{ color: colors.success }} />
              </Card>
            </Col>
            <Col xs={24} sm={12} md={6} lg={3}>
              <Card hoverable style={{ borderLeft: `3px solid ${result.summary['亏损门店'] > 0 ? colors.danger : colors.success}` }}>
                <Statistic
                  title="亏损门店"
                  value={result.summary['亏损门店']}
                  prefix={<AlertOutlined />}
                  valueStyle={{ color: result.summary['亏损门店'] > 0 ? colors.danger : colors.success }}
                />
              </Card>
            </Col>
            <Col xs={24} sm={12} md={6} lg={4}>
              <Card hoverable style={{ borderLeft: `3px solid ${getRiskColor(result.summary['风险等级']) === 'green' ? colors.success : colors.danger}` }}>
                <div style={{ fontSize: 12, color: colors.textTertiary, marginBottom: 4, textTransform: 'uppercase', letterSpacing: 0.5, fontWeight: 500 }}>风险等级</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Tooltip title={riskMap[result.summary['风险等级']]?.desc}>
                    <Tag color={getRiskColor(result.summary['风险等级'])} style={{ fontSize: 12, fontWeight: 600, cursor: 'help' }}>
                      {riskMap[result.summary['风险等级']]?.label || result.summary['风险等级']}
                    </Tag>
                  </Tooltip>
                  <span style={{ fontSize: 22, fontWeight: 700, color: getRiskColor(result.summary['风险等级']) === 'green' ? colors.success : colors.danger, fontFamily: '"Fira Code", monospace' }}>
                    {Number(result.summary['风险分']).toPrecision(4)}
                  </span>
                </div>
              </Card>
            </Col>
          </Row>

          {/* 图表 */}
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col xs={24} lg={12}>
              <Card>
                <ReactECharts option={getAllocationPieOption()} style={{ height: 350 }} />
              </Card>
            </Col>
            <Col xs={24} lg={12}>
              <Card>
                <ReactECharts option={getGrowthBarOption()} style={{ height: 350 }} />
              </Card>
            </Col>
          </Row>

          {/* 建议 */}
          {result.recommendations?.length > 0 && (
            <Card title="风险建议" style={{ marginBottom: 16, borderLeft: `3px solid ${colors.warning}` }}>
              {result.recommendations.map((rec, i) => (
                <p key={i} style={{ margin: '6px 0', color: colors.textSecondary }}>{rec}</p>
              ))}
            </Card>
          )}

          {/* 分配明细表格 */}
          <Card title="门店分配明细">
            <Table
              dataSource={result.allocation_detail}
              rowKey="store_code"
              size="small"
              pagination={{ pageSize: 20 }}
              columns={[
                { title: '门店编码', dataIndex: 'store_code', sorter: (a, b) => a.store_code.localeCompare(b.store_code) },
                { title: '基线', dataIndex: 'baseline', render: v => `¥${v.toLocaleString()}`, sorter: (a, b) => a.baseline - b.baseline },
                { title: '目标', dataIndex: 'target', render: v => `¥${v.toLocaleString()}`, sorter: (a, b) => a.target - b.target },
                { title: '承压率', dataIndex: 'pressure_ratio', sorter: (a, b) => parseFloat(a.pressure_ratio) - parseFloat(b.pressure_ratio) },
                { title: '增长率', dataIndex: 'growth_rate', sorter: (a, b) => parseFloat(a.growth_rate) - parseFloat(b.growth_rate) },
              ]}
            />
          </Card>
        </>
      )}
    </div>
  )
}
