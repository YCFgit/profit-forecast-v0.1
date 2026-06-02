import { useState, useEffect } from 'react'
import { Card, Row, Col, Statistic, Button, Spin, message, Table, Tag, Tabs, Empty } from 'antd'
import {
  RiseOutlined,
  FallOutlined,
  CalendarOutlined,
  ShopOutlined,
  SwapOutlined,
} from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import { predictYoy } from '../api'
import { colors, chartColors } from '../theme'

const formatMoney = (v) => {
  if (v >= 1e8) return `¥${(v / 1e8).toFixed(2)}亿`
  if (v >= 1e4) return `¥${(v / 1e4).toFixed(0)}万`
  return `¥${v.toLocaleString()}`
}

export default function Forecast() {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)

  // 页面加载时自动执行同比预测
  useEffect(() => {
    handlePredict()
  }, [])

  const handlePredict = async () => {
    setLoading(true)
    try {
      const res = await predictYoy()
      setResult(res.data)
      message.success('同比预测完成')
    } catch (err) {
      message.error('预测失败: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const getCompareBarOption = () => {
    if (!result) return {}
    const top = result.top_stores.slice(0, 10)
    return {
      title: {
        text: 'Top 10 门店 — 本月 vs 下月预测',
        left: 'center',
        textStyle: { fontSize: 14, color: colors.text },
      },
      tooltip: {
        trigger: 'axis',
        formatter: (params) => {
          let s = params[0].name + '<br/>'
          params.forEach(p => {
            s += `${p.marker} ${p.seriesName}: ${formatMoney(p.value)}<br/>`
          })
          return s
        },
      },
      legend: { bottom: 0 },
      grid: { top: 40, bottom: 50, left: 60, right: 20 },
      xAxis: {
        type: 'category',
        data: top.map(d => d.store_code),
        axisLabel: { rotate: 45, fontSize: 11 },
      },
      yAxis: {
        type: 'value',
        axisLabel: { formatter: (v) => formatMoney(v) },
      },
      series: [
        {
          name: '上月实际',
          type: 'bar',
          data: top.map(d => d.last_month),
          itemStyle: { color: chartColors[0], borderRadius: [4, 4, 0, 0] },
          barMaxWidth: 20,
        },
        {
          name: '去年同月',
          type: 'bar',
          data: top.map(d => d.last_year_same),
          itemStyle: { color: chartColors[1], borderRadius: [4, 4, 0, 0] },
          barMaxWidth: 20,
        },
        {
          name: `${result.current_month.month} 预测`,
          type: 'bar',
          data: top.map(d => d.pred_current),
          itemStyle: { color: chartColors[2], borderRadius: [4, 4, 0, 0] },
          barMaxWidth: 20,
        },
        {
          name: `${result.next_month.month} 预测`,
          type: 'bar',
          data: top.map(d => d.pred_next),
          itemStyle: { color: chartColors[3], borderRadius: [4, 4, 0, 0] },
          barMaxWidth: 20,
        },
      ],
    }
  }

  const getTrendLineOption = () => {
    if (!result) return {}
    // 取 top 5 门店的趋势
    const top5 = result.top_stores.slice(0, 5)
    return {
      title: {
        text: 'Top 5 门店 — 信号对比',
        left: 'center',
        textStyle: { fontSize: 14, color: colors.text },
      },
      tooltip: {
        trigger: 'axis',
        formatter: (params) => {
          let s = params[0].name + '<br/>'
          params.forEach(p => {
            s += `${p.marker} ${p.seriesName}: ${formatMoney(p.value)}<br/>`
          })
          return s
        },
      },
      legend: { bottom: 0 },
      grid: { top: 40, bottom: 50, left: 60, right: 20 },
      xAxis: {
        type: 'category',
        data: top5.map(d => d.store_code),
      },
      yAxis: {
        type: 'value',
        axisLabel: { formatter: (v) => formatMoney(v) },
      },
      series: [
        {
          name: '上月 (LM)',
          type: 'line',
          data: top5.map(d => d.last_month),
          itemStyle: { color: chartColors[0] },
          symbol: 'circle',
          symbolSize: 8,
        },
        {
          name: '去年同月 (LY)',
          type: 'line',
          data: top5.map(d => d.last_year_same),
          itemStyle: { color: chartColors[1] },
          symbol: 'diamond',
          symbolSize: 8,
        },
        {
          name: '去年下月 (LY_NM)',
          type: 'line',
          data: top5.map(d => d.last_year_next),
          itemStyle: { color: chartColors[4] },
          symbol: 'triangle',
          symbolSize: 8,
        },
        {
          name: '本月预测',
          type: 'line',
          data: top5.map(d => d.pred_current),
          itemStyle: { color: chartColors[2] },
          lineStyle: { type: 'dashed', width: 2 },
          symbol: 'rect',
          symbolSize: 8,
        },
        {
          name: '下月预测',
          type: 'line',
          data: top5.map(d => d.pred_next),
          itemStyle: { color: chartColors[3] },
          lineStyle: { type: 'dashed', width: 2 },
          symbol: 'roundRect',
          symbolSize: 8,
        },
      ],
    }
  }

  const columns = [
    {
      title: '门店编码',
      dataIndex: 'store_code',
      sorter: (a, b) => a.store_code.localeCompare(b.store_code),
      fixed: 'left',
      width: 100,
    },
    {
      title: '上月实际',
      dataIndex: 'last_month',
      render: v => formatMoney(v),
      sorter: (a, b) => a.last_month - b.last_month,
      align: 'right',
    },
    {
      title: '去年同月',
      dataIndex: 'last_year_same',
      render: v => formatMoney(v),
      sorter: (a, b) => a.last_year_same - b.last_year_same,
      align: 'right',
    },
    {
      title: '去年下月',
      dataIndex: 'last_year_next',
      render: v => formatMoney(v),
      sorter: (a, b) => a.last_year_next - b.last_year_next,
      align: 'right',
    },
    {
      title: '本月预测',
      dataIndex: 'pred_current',
      render: v => <strong>{formatMoney(v)}</strong>,
      sorter: (a, b) => a.pred_current - b.pred_current,
      align: 'right',
    },
    {
      title: '下月预测',
      dataIndex: 'pred_next',
      render: v => <strong>{formatMoney(v)}</strong>,
      sorter: (a, b) => a.pred_next - b.pred_next,
      align: 'right',
    },
    {
      title: '环比',
      key: 'mom',
      render: (_, r) => {
        if (!r.last_month || r.last_month === 0) return '-'
        const pct = ((r.pred_current - r.last_month) / r.last_month * 100).toFixed(1)
        const isUp = pct >= 0
        return (
          <Tag color={isUp ? 'green' : 'red'} style={{ fontWeight: 600 }}>
            {isUp ? <RiseOutlined /> : <FallOutlined />} {isUp ? '+' : ''}{pct}%
          </Tag>
        )
      },
      align: 'center',
    },
    {
      title: '同比',
      key: 'yoy',
      render: (_, r) => {
        if (!r.last_year_same || r.last_year_same === 0) return '-'
        const pct = ((r.pred_current - r.last_year_same) / r.last_year_same * 100).toFixed(1)
        const isUp = pct >= 0
        return (
          <Tag color={isUp ? 'green' : 'red'} style={{ fontWeight: 600 }}>
            {isUp ? <RiseOutlined /> : <FallOutlined />} {isUp ? '+' : ''}{pct}%
          </Tag>
        )
      },
      align: 'center',
    },
  ]

  return (
    <div>
      {/* 触发按钮 */}
      <Card style={{ marginBottom: 16, borderTop: `3px solid ${colors.primary}` }}>
        <Row gutter={16} align="middle">
          <Col flex="auto">
            <div style={{ color: colors.textSecondary }}>
              <CalendarOutlined style={{ marginRight: 8 }} />
              基于 <strong>上月实际</strong>（权重 40%）、<strong>去年同月</strong>（35%）、<strong>去年下月</strong>（25%）
              三信号加权融合，预测本月及下月销售额
            </div>
          </Col>
          <Col>
            <Button
              type="primary"
              icon={<SwapOutlined />}
              onClick={handlePredict}
              loading={loading}
              size="large"
            >
              同比预测
            </Button>
          </Col>
        </Row>
      </Card>

      {loading && <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />}

      {!result && !loading && (
        <Card>
          <Empty description="点击「同比预测」按钮生成预测结果" />
        </Card>
      )}

      {result && !loading && (
        <>
          {/* 汇总卡片 */}
          <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
            <Col xs={24} sm={12} md={6}>
              <Card hoverable style={{ borderLeft: `3px solid ${colors.primary}` }}>
                <Statistic
                  title={`${result.current_month.month} 预测总额`}
                  value={result.current_month.total}
                  formatter={(v) => formatMoney(v)}
                  prefix={<RiseOutlined style={{ color: colors.primary }} />}
                />
                <div style={{ fontSize: 12, color: colors.textTertiary, marginTop: 4 }}>
                  {result.current_month.store_count} 家门店
                </div>
              </Card>
            </Col>
            <Col xs={24} sm={12} md={6}>
              <Card hoverable style={{ borderLeft: `3px solid ${colors.accent}` }}>
                <Statistic
                  title={`${result.next_month.month} 预测总额`}
                  value={result.next_month.total}
                  formatter={(v) => formatMoney(v)}
                  prefix={<RiseOutlined style={{ color: colors.accent }} />}
                />
                <div style={{ fontSize: 12, color: colors.textTertiary, marginTop: 4 }}>
                  {result.next_month.store_count} 家门店
                </div>
              </Card>
            </Col>
            <Col xs={24} sm={12} md={6}>
              <Card hoverable style={{ borderLeft: `3px solid ${colors.success}` }}>
                <Statistic
                  title="月环比增长"
                  value={((result.next_month.total - result.current_month.total) / result.current_month.total * 100).toFixed(1)}
                  suffix="%"
                  prefix={<RiseOutlined style={{ color: colors.success }} />}
                  valueStyle={{ color: colors.success }}
                />
              </Card>
            </Col>
            <Col xs={24} sm={12} md={6}>
              <Card hoverable style={{ borderLeft: `3px solid ${colors.primaryLight}` }}>
                <Statistic
                  title="店均预测（本月）"
                  value={result.current_month.total / result.current_month.store_count}
                  formatter={(v) => formatMoney(v)}
                  prefix={<ShopOutlined style={{ color: colors.primaryLight }} />}
                />
              </Card>
            </Col>
          </Row>

          {/* 图表 */}
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col xs={24} lg={14}>
              <Card>
                <ReactECharts option={getCompareBarOption()} style={{ height: 380 }} />
              </Card>
            </Col>
            <Col xs={24} lg={10}>
              <Card>
                <ReactECharts option={getTrendLineOption()} style={{ height: 380 }} />
              </Card>
            </Col>
          </Row>

          {/* 门店明细表格 */}
          <Card title={`门店预测明细（${result.store_details.length} 家）`}>
            <Table
              dataSource={result.store_details}
              rowKey="store_code"
              size="small"
              pagination={{ pageSize: 20, showSizeChanger: true, showTotal: t => `共 ${t} 家` }}
              scroll={{ x: 900 }}
              columns={columns}
            />
          </Card>
        </>
      )}
    </div>
  )
}
