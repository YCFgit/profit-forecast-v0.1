import { useState, useEffect } from 'react'
import { Card, Row, Col, Button, InputNumber, Spin, message, Table, Tag, Descriptions, List, Tooltip } from 'antd'
import ReactECharts from 'echarts-for-react'
import { assessRisk, runMonteCarlo } from '../api'
import { colors, chartColors } from '../theme'

export default function Risk() {
  const [loading, setLoading] = useState(false)
  const [target, setTarget] = useState(10000000)
  const [result, setResult] = useState(null)

  const handleAssess = async (t) => {
    setLoading(true)
    try {
      const res = await assessRisk(t ?? target)
      setResult(res.data)
      message.success('评估完成')
    } catch (err) {
      message.error('评估失败: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  // 页面加载时自动执行默认评估
  useEffect(() => {
    handleAssess(10000000)
  }, [])

  const riskMap = {
    low:      { color: 'green', label: '低风险', desc: '目标可达，承压均匀' },
    medium:   { color: 'orange', label: '中风险', desc: '需关注个别门店' },
    high:     { color: 'red', label: '高风险', desc: '目标激进，需调整' },
    critical: { color: 'red', label: '极高风险', desc: '建议重新制定方案' },
  }
  const getRiskColor = (level) => riskMap[level]?.color || 'default'
  const getRiskLabel = (level) => riskMap[level]?.label || level

  const getRadarOption = () => {
    if (!result) return {}
    return {
      title: { text: '风险因素雷达图', left: 'center', textStyle: { fontSize: 14, color: colors.text } },
      tooltip: {},
      radar: {
        indicator: result.factors.map(f => ({ name: f.name, max: 100 })),
        axisName: { color: colors.textSecondary, fontSize: 11 },
        splitArea: { areaStyle: { color: ['#FAFBFD', '#F8FAFC', '#F1F5F9', '#E2E8F0'] } },
      },
      series: [{
        type: 'radar',
        data: [{
          value: result.factors.map(f => f.score),
          name: '风险分数',
          areaStyle: { color: 'rgba(220, 38, 38, 0.15)' },
          lineStyle: { color: colors.danger, width: 2 },
          itemStyle: { color: colors.danger },
        }],
      }],
    }
  }

  const getFactorBarOption = () => {
    if (!result) return {}
    return {
      title: { text: '各风险因素分数', left: 'center', textStyle: { fontSize: 14, color: colors.text } },
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'category',
        data: result.factors.map(f => f.name),
        axisLabel: { fontSize: 11 },
      },
      yAxis: { type: 'value', max: 100, name: '风险分' },
      grid: { top: 40, bottom: 30, left: 50, right: 20 },
      series: [{
        type: 'bar',
        data: result.factors.map(f => ({
          value: f.score,
          itemStyle: {
            color: f.level === 'low' ? colors.success : f.level === 'medium' ? colors.warning : colors.danger,
            borderRadius: [4, 4, 0, 0],
          },
        })),
        barMaxWidth: 36,
        label: { show: true, position: 'top', formatter: '{c}', fontSize: 11 },
      }],
    }
  }

  const getMonteCarloOption = () => {
    if (!result?.monte_carlo) return {}
    const mc = result.monte_carlo
    return {
      title: { text: '蒙特卡洛利润模拟', left: 'center', textStyle: { fontSize: 14, color: colors.text } },
      tooltip: {},
      series: [{
        type: 'gauge',
        progress: { show: true },
        detail: { valueAnimation: true, formatter: '{value}%', fontSize: 20 },
        data: [{ value: parseFloat(mc.loss_probability), name: '亏损概率' }],
        axisLine: { lineStyle: { width: 20, color: [[0.1, colors.success], [0.3, colors.warning], [1, colors.danger]] } },
        min: 0,
        max: 50,
      }],
    }
  }

  const factorColumns = [
    { title: '风险因素', dataIndex: 'name' },
    {
      title: '风险分数',
      dataIndex: 'score',
      sorter: (a, b) => a.score - b.score,
      render: v => <span style={{ fontWeight: 'bold' }}>{v}</span>,
    },
    {
      title: '风险等级',
      dataIndex: 'level',
      render: v => <Tag color={getRiskColor(v)}>{getRiskLabel(v)}</Tag>,
      filters: [
        { text: '低风险', value: 'low' },
        { text: '中风险', value: 'medium' },
        { text: '高风险', value: 'high' },
        { text: '极高风险', value: 'critical' },
      ],
      onFilter: (value, record) => record.level === value,
    },
    { title: '说明', dataIndex: 'description' },
    { title: '影响门店数', dataIndex: 'affected_stores', sorter: (a, b) => a.affected_stores - b.affected_stores },
  ]

  const highRiskColumns = [
    { title: '门店编码', dataIndex: '门店编码' },
    { title: '基线', dataIndex: '基线', render: v => `¥${v?.toLocaleString()}` },
    { title: '目标', dataIndex: '目标', render: v => `¥${v?.toLocaleString()}` },
    { title: '目标/基线', dataIndex: '目标/基线' },
    { title: '风险等级', dataIndex: '风险等级', render: v => <Tag color={getRiskColor(v)}>{getRiskLabel(v)}</Tag> },
    { title: '风险分数', dataIndex: '风险分数', sorter: (a, b) => a['风险分数'] - b['风险分数'] },
    { title: '建议', dataIndex: '建议' },
  ]

  return (
    <div>
      <Card style={{ marginBottom: 16, borderTop: `3px solid ${colors.danger}` }}>
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
            <Button type="primary" onClick={handleAssess} loading={loading}>
              风险评估
            </Button>
          </Col>
        </Row>
      </Card>

      {loading && <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />}

      {result && !loading && (
        <>
          {/* 综合风险 */}
          <Card style={{ marginBottom: 16 }}>
            <Descriptions bordered column={4} size="small">
              <Descriptions.Item label="综合风险分">
                <span style={{ fontSize: 24, fontWeight: 'bold', color: getRiskColor(result.overall_level) === 'green' ? colors.success : colors.danger }}>
                  {result.overall_score}
                </span>
              </Descriptions.Item>
              <Descriptions.Item label="风险等级">
                <Tooltip title={riskMap[result.overall_level]?.desc}>
                  <Tag color={getRiskColor(result.overall_level)} style={{ fontSize: 14, padding: '4px 12px', cursor: 'help' }}>
                    {getRiskLabel(result.overall_level)}
                  </Tag>
                </Tooltip>
              </Descriptions.Item>
              <Descriptions.Item label="高风险门店">{result.high_risk_stores?.length || 0} 家</Descriptions.Item>
              <Descriptions.Item label="建议数">{result.recommendations?.length || 0} 条</Descriptions.Item>
            </Descriptions>
          </Card>

          {/* 图表 */}
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col xs={24} lg={result.monte_carlo ? 8 : 12}>
              <Card>
                <ReactECharts option={getRadarOption()} style={{ height: 350 }} />
              </Card>
            </Col>
            <Col xs={24} lg={result.monte_carlo ? 8 : 12}>
              <Card>
                <ReactECharts option={getFactorBarOption()} style={{ height: 350 }} />
              </Card>
            </Col>
            {result.monte_carlo && (
              <Col xs={24} lg={8}>
                <Card>
                  <ReactECharts option={getMonteCarloOption()} style={{ height: 350 }} />
                </Card>
              </Col>
            )}
          </Row>

          {/* 蒙特卡洛指标 */}
          {result.monte_carlo && (
            <Card style={{ marginBottom: 16 }}>
              <Descriptions bordered column={5} size="small">
                <Descriptions.Item label="利润均值">¥{result.monte_carlo.profit_mean?.toLocaleString()}</Descriptions.Item>
                <Descriptions.Item label="利润标准差">¥{result.monte_carlo.profit_std?.toLocaleString()}</Descriptions.Item>
                <Descriptions.Item label="亏损概率">{result.monte_carlo.loss_probability}</Descriptions.Item>
                <Descriptions.Item label="VaR95">¥{result.monte_carlo.var_95?.toLocaleString()}</Descriptions.Item>
                <Descriptions.Item label="CVaR95">¥{result.monte_carlo.cvar_95?.toLocaleString()}</Descriptions.Item>
              </Descriptions>
            </Card>
          )}

          {/* 建议 */}
          <Card title="风险建议" style={{ marginBottom: 16, borderLeft: `3px solid ${colors.warning}` }}>
            <List
              dataSource={result.recommendations}
              renderItem={(item) => <List.Item style={{ color: colors.textSecondary }}>{item}</List.Item>}
            />
          </Card>

          {/* 风险因素明细 */}
          <Card title="风险因素明细" style={{ marginBottom: 16 }}>
            <Table
              dataSource={result.factors}
              rowKey="name"
              size="small"
              pagination={false}
              columns={factorColumns}
            />
          </Card>

          {/* 高风险门店 */}
          {result.high_risk_stores?.length > 0 && (
            <Card title="高风险门店明细">
              <Table
                dataSource={result.high_risk_stores}
                rowKey="门店编码"
                size="small"
                pagination={{ pageSize: 20 }}
                columns={highRiskColumns}
              />
            </Card>
          )}
        </>
      )}
    </div>
  )
}
