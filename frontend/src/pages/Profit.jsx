import { useState } from 'react'
import { Card, Row, Col, Button, InputNumber, Spin, message, Table, Descriptions } from 'antd'
import ReactECharts from 'echarts-for-react'
import { calculateProfit } from '../api'
import { colors, chartColors } from '../theme'

export default function Profit() {
  const [loading, setLoading] = useState(false)
  const [target, setTarget] = useState(10000000)
  const [result, setResult] = useState(null)

  const handleCalculate = async () => {
    setLoading(true)
    try {
      const res = await calculateProfit(target)
      setResult(res.data)
      message.success('测算完成')
    } catch (err) {
      message.error('测算失败: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const getPnLOption = () => {
    if (!result) return {}
    const pnl = result.pnl
    const categories = pnl.map(r => r['项目'])
    const values = pnl.map(r => r['金额'] || 0)

    return {
      title: { text: '利润表 (P&L)', left: 'center', textStyle: { fontSize: 14, color: colors.text } },
      tooltip: { trigger: 'axis', formatter: (p) => `${p[0].name}: ¥${p[0].value.toLocaleString()}` },
      xAxis: {
        type: 'category',
        data: categories,
        axisLabel: { rotate: 30, fontSize: 10 },
      },
      yAxis: { type: 'value', axisLabel: { formatter: (v) => `${(v / 10000).toFixed(0)}万` } },
      grid: { top: 40, bottom: 70, left: 60, right: 20 },
      series: [{
        type: 'bar',
        data: values.map((v, i) => ({
          value: v,
          itemStyle: {
            color: v >= 0 ? (i === pnl.length - 1 ? colors.success : colors.primary) : colors.danger,
            borderRadius: [4, 4, 0, 0],
          },
        })),
        barMaxWidth: 36,
        label: { show: true, position: 'top', formatter: (p) => `¥${(p.value / 10000).toFixed(0)}万`, fontSize: 10 },
      }],
    }
  }

  const getComparisonOption = () => {
    if (!result) return {}
    const data = result.comparison.slice(0, 15)
    return {
      title: { text: '基线 vs 目标净利 (Top 15)', left: 'center', textStyle: { fontSize: 14, color: colors.text } },
      tooltip: { trigger: 'axis' },
      legend: { data: ['基线净利', '目标净利'], top: 28, textStyle: { fontSize: 11 } },
      xAxis: {
        type: 'category',
        data: data.map(d => d['门店编码']),
        axisLabel: { rotate: 45, fontSize: 11 },
      },
      yAxis: { type: 'value', axisLabel: { formatter: (v) => `${(v / 10000).toFixed(0)}万` } },
      grid: { top: 50, bottom: 70, left: 60, right: 20 },
      series: [
        {
          name: '基线净利',
          type: 'bar',
          data: data.map(d => d['基线净利']),
          itemStyle: { color: colors.primaryBg, borderRadius: [4, 4, 0, 0] },
          barMaxWidth: 24,
        },
        {
          name: '目标净利',
          type: 'bar',
          data: data.map(d => d['目标净利']),
          itemStyle: { color: colors.primary, borderRadius: [4, 4, 0, 0] },
          barMaxWidth: 24,
        },
      ],
    }
  }

  const getRankingOption = () => {
    if (!result) return {}
    const top5 = result.top_stores.slice(0, 5)
    const bottom5 = result.bottom_stores.slice(0, 5)
    return {
      title: { text: '门店净利排行', left: 'center', textStyle: { fontSize: 14, color: colors.text } },
      tooltip: { trigger: 'axis' },
      legend: { data: ['Top 5', 'Bottom 5'], top: 28, textStyle: { fontSize: 11 } },
      xAxis: {
        type: 'category',
        data: [...top5.map(d => d['门店编码']), ...bottom5.map(d => d['门店编码'])],
        axisLabel: { fontSize: 11 },
      },
      yAxis: { type: 'value', axisLabel: { formatter: (v) => `${(v / 10000).toFixed(0)}万` } },
      grid: { top: 50, bottom: 30, left: 60, right: 20 },
      series: [
        {
          name: 'Top 5',
          type: 'bar',
          data: [...top5.map(d => d['净利润']), ...new Array(5).fill(null)],
          itemStyle: { color: colors.success, borderRadius: [4, 4, 0, 0] },
          barMaxWidth: 32,
        },
        {
          name: 'Bottom 5',
          type: 'bar',
          data: [...new Array(5).fill(null), ...bottom5.map(d => d['净利润'])],
          itemStyle: { color: colors.danger, borderRadius: [4, 4, 0, 0] },
          barMaxWidth: 32,
        },
      ],
    }
  }

  const comparisonColumns = [
    { title: '门店编码', dataIndex: '门店编码' },
    { title: '基线收入', dataIndex: '基线收入', render: v => `¥${v.toLocaleString()}` },
    { title: '目标收入', dataIndex: '目标收入', render: v => `¥${v.toLocaleString()}` },
    { title: '收入增长', dataIndex: '收入增长' },
    { title: '基线净利', dataIndex: '基线净利', render: v => `¥${v.toLocaleString()}` },
    { title: '目标净利', dataIndex: '目标净利', render: v => `¥${v.toLocaleString()}` },
    { title: '净利增长', dataIndex: '净利增长', render: v => `¥${v.toLocaleString()}` },
  ]

  return (
    <div>
      <Card style={{ marginBottom: 16, borderTop: `3px solid ${colors.success}` }}>
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
            <Button type="primary" onClick={handleCalculate} loading={loading}>
              测算利润
            </Button>
          </Col>
        </Row>
      </Card>

      {loading && <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />}

      {result && !loading && (
        <>
          <Card style={{ marginBottom: 16 }}>
            <Descriptions bordered column={4} size="small">
              <Descriptions.Item label="总收入">¥{result.summary['总收入']?.toLocaleString()}</Descriptions.Item>
              <Descriptions.Item label="总毛利">¥{result.summary['总毛利']?.toLocaleString()}</Descriptions.Item>
              <Descriptions.Item label="毛利率">{(result.summary['平均毛利率'] * 100).toFixed(1)}%</Descriptions.Item>
              <Descriptions.Item label="总净利润">
                <span style={{ color: result.summary['总净利润'] > 0 ? colors.success : colors.danger, fontWeight: 'bold' }}>
                  ¥{result.summary['总净利润']?.toLocaleString()}
                </span>
              </Descriptions.Item>
              <Descriptions.Item label="总运营费用">¥{result.summary['总运营费用']?.toLocaleString()}</Descriptions.Item>
              <Descriptions.Item label="总营业利润">¥{result.summary['总营业利润']?.toLocaleString()}</Descriptions.Item>
              <Descriptions.Item label="营业利润率">{(result.summary['平均营业利润率'] * 100).toFixed(1)}%</Descriptions.Item>
              <Descriptions.Item label="净利率">{(result.summary['平均净利率'] * 100).toFixed(1)}%</Descriptions.Item>
            </Descriptions>
          </Card>

          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col xs={24} lg={12}>
              <Card>
                <ReactECharts option={getPnLOption()} style={{ height: 350 }} />
              </Card>
            </Col>
            <Col xs={24} lg={12}>
              <Card>
                <ReactECharts option={getRankingOption()} style={{ height: 350 }} />
              </Card>
            </Col>
          </Row>

          <Card style={{ marginBottom: 16 }}>
            <ReactECharts option={getComparisonOption()} style={{ height: 350 }} />
          </Card>

          <Card title="基线 vs 目标明细">
            <Table
              dataSource={result.comparison}
              rowKey="门店编码"
              size="small"
              pagination={{ pageSize: 20 }}
              columns={comparisonColumns}
            />
          </Card>
        </>
      )}
    </div>
  )
}
