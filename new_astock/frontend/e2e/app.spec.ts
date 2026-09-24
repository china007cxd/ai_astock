import { expect, test } from '@playwright/test'

test('应用壳和主要导航可用', async ({ page }) => {
  await page.goto('/dashboard')
  await expect(page.getByLabel('new_astock')).toBeVisible()
  await expect(page.getByText('大盘复盘', { exact: true }).first()).toBeVisible()
  await page.getByText('系统设置', { exact: true }).click()
  await expect(page.getByRole('heading', { name: '系统设置' })).toBeVisible()
})
