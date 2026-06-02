import { useEffect, useRef } from 'react'
import { predictYoy, runPipeline, allocateTargets, calculateProfit, assessRisk } from '../api'

/**
 * 应用级预取 Hook
 * 在 App 挂载时预热后端缓存，后续页面切换直接命中缓存
 */
export function usePrefetch() {
  const prefetched = useRef(false)

  useEffect(() => {
    if (prefetched.current) return
    prefetched.current = true

    // 后台预热最常用的接口（不阻塞 UI）
    const warmup = async () => {
      try {
        // 1. 先预热同比预测（最快返回的接口，会缓存 stores + monthly_metrics）
        await predictYoy()
        console.log('[Prefetch] predict-yoy 缓存已预热')

        // 2. 并行预热其他接口
        Promise.allSettled([
          runPipeline(10000000, 'mysql'),
          allocateTargets(10000000, true),
          calculateProfit(10000000),
          assessRisk(10000000),
        ]).then(() => {
          console.log('[Prefetch] 所有接口缓存已预热')
        })
      } catch (e) {
        console.warn('[Prefetch] 预热失败:', e)
      }
    }

    warmup()
  }, [])
}
