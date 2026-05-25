/**
 * 鞋服零售利润测算系统 — 统一设计主题
 * 基于 ui-ux-pro-max 设计系统：Data-Dense Dashboard
 * Primary: #1E40AF | Accent: #D97706 | Background: #F8FAFC
 */

const theme = {
  token: {
    // 主色系
    colorPrimary: '#1E40AF',
    colorPrimaryBg: '#DBEAFE',
    colorPrimaryBgHover: '#BFDBFE',
    colorPrimaryBorder: '#93C5FD',
    colorPrimaryBorderHover: '#60A5FA',
    colorPrimaryHover: '#1D4ED8',
    colorPrimaryActive: '#1E3A8A',
    colorPrimaryTextHover: '#2563EB',
    colorPrimaryText: '#1E40AF',
    colorPrimaryTextActive: '#1E3A8A',

    // 成功/警告/错误
    colorSuccess: '#16A34A',
    colorWarning: '#D97706',
    colorError: '#DC2626',
    colorInfo: '#2563EB',

    // 文字
    colorText: '#0F172A',
    colorTextSecondary: '#475569',
    colorTextTertiary: '#94A3B8',
    colorTextQuaternary: '#CBD5E1',

    // 背景
    colorBgLayout: '#F1F5F9',
    colorBgContainer: '#FFFFFF',
    colorBgElevated: '#FFFFFF',
    colorBgSpotlight: '#F8FAFC',

    // 边框
    colorBorder: '#E2E8F0',
    colorBorderSecondary: '#F1F5F9',

    // 填充
    colorFill: '#E2E8F0',
    colorFillSecondary: '#F1F5F9',
    colorFillTertiary: '#F8FAFC',
    colorFillQuaternary: '#FAFBFD',

    // 字体
    fontFamily: '"Fira Sans", -apple-system, "PingFang SC", "Microsoft YaHei", "Helvetica Neue", sans-serif',
    fontSize: 14,
    fontSizeHeading1: 30,
    fontSizeHeading2: 22,
    fontSizeHeading3: 18,
    fontSizeHeading4: 16,
    fontSizeHeading5: 14,

    // 圆角
    borderRadius: 8,
    borderRadiusLG: 12,
    borderRadiusSM: 6,
    borderRadiusXS: 4,

    // 间距
    marginLG: 24,
    marginMD: 16,
    marginSM: 12,
    marginXS: 8,
    paddingLG: 24,
    paddingMD: 16,
    paddingSM: 12,
    paddingXS: 8,

    // 阴影
    boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.06), 0 1px 2px -1px rgba(0, 0, 0, 0.06)',
    boxShadowSecondary: '0 4px 6px -1px rgba(0, 0, 0, 0.07), 0 2px 4px -2px rgba(0, 0, 0, 0.05)',

    // 动效
    motionDurationMid: '0.2s',
    motionDurationSlow: '0.3s',
  },
  components: {
    Layout: {
      siderBg: '#0F172A',
      headerBg: '#FFFFFF',
      bodyBg: '#F1F5F9',
      triggerBg: '#1E293B',
    },
    Menu: {
      darkItemBg: '#0F172A',
      darkItemSelectedBg: '#1E40AF',
      darkItemHoverBg: '#1E293B',
      darkItemColor: '#94A3B8',
      darkItemSelectedColor: '#FFFFFF',
      itemHeight: 44,
      itemMarginInline: 8,
      itemBorderRadius: 8,
    },
    Card: {
      paddingLG: 20,
      borderRadiusLG: 12,
    },
    Table: {
      headerBg: '#F8FAFC',
      headerColor: '#475569',
      headerSortActiveBg: '#EFF6FF',
      rowHoverBg: '#F8FAFC',
      borderColor: '#F1F5F9',
      cellPaddingBlock: 10,
      cellPaddingInline: 14,
    },
    Button: {
      primaryShadow: '0 1px 2px 0 rgba(30, 64, 175, 0.2)',
      defaultBorderColor: '#E2E8F0',
    },
    Statistic: {
      titleFontSize: 12,
      contentFontSize: 22,
    },
    Tag: {
      borderRadiusSM: 4,
    },
    Descriptions: {
      labelBg: '#F8FAFC',
    },
    InputNumber: {
      paddingBlock: 6,
      paddingInline: 10,
    },
    Tooltip: {
      colorBgSpotlight: '#0F172A',
      colorTextLightSolid: '#FFFFFF',
    },
  },
}

export default theme

// 设计系统色彩常量（供 ECharts 等非 Ant Design 组件使用）
export const colors = {
  primary: '#1E40AF',
  primaryLight: '#3B82F6',
  primaryBg: '#DBEAFE',
  accent: '#D97706',
  accentLight: '#F59E0B',
  success: '#16A34A',
  successLight: '#22C55E',
  warning: '#D97706',
  warningLight: '#F59E0B',
  danger: '#DC2626',
  dangerLight: '#EF4444',
  text: '#0F172A',
  textSecondary: '#475569',
  textTertiary: '#94A3B8',
  bg: '#F1F5F9',
  surface: '#FFFFFF',
  border: '#E2E8F0',
  muted: '#F8FAFC',
}

// ECharts 图表配色方案
export const chartColors = [
  '#1E40AF', // primary
  '#D97706', // accent
  '#16A34A', // success
  '#DC2626', // danger
  '#7C3AED', // violet
  '#0891B2', // cyan
  '#DB2777', // pink
  '#65A30D', // lime
  '#EA580C', // orange
  '#4F46E5', // indigo
]
