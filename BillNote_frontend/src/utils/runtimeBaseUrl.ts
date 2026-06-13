const DESKTOP_BACKEND_HOST = '127.0.0.1'
const DESKTOP_BACKEND_PORT = __DESKTOP_BACKEND_PORT__
const DESKTOP_BUILD_MODE = 'tauri'

function stripTrailingSlash(url: string) {
  return url.replace(/\/$/, '')
}

function stripApiSuffix(url: string) {
  return stripTrailingSlash(url).replace(/\/api$/, '')
}

export function isDesktopBuildMode(mode = import.meta.env.MODE) {
  return mode === DESKTOP_BUILD_MODE
}

export function resolveApiBaseUrl() {
  const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL
  if (configuredBaseUrl) {
    return stripTrailingSlash(configuredBaseUrl)
  }

  if (isDesktopBuildMode()) {
    return `http://${DESKTOP_BACKEND_HOST}:${DESKTOP_BACKEND_PORT}/api`
  }

  return '/api'
}

export function resolveStaticBaseUrl() {
  const configuredScreenshotBaseUrl = import.meta.env.VITE_SCREENSHOT_BASE_URL
  if (configuredScreenshotBaseUrl) {
    return stripTrailingSlash(
      configuredScreenshotBaseUrl.replace(/\/static\/screenshots$/, '')
    )
  }

  const configuredApiBaseUrl = import.meta.env.VITE_API_BASE_URL
  if (configuredApiBaseUrl) {
    return stripApiSuffix(configuredApiBaseUrl)
  }

  if (isDesktopBuildMode()) {
    return `http://${DESKTOP_BACKEND_HOST}:${DESKTOP_BACKEND_PORT}`
  }

  return ''
}

export const runtimeApiBaseUrl = resolveApiBaseUrl()
export const runtimeStaticBaseUrl = resolveStaticBaseUrl()
