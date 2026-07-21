import { useState } from 'react'
import { Bug, Wifi, AlertTriangle, Github, X } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { useCrawlerStore } from '@/store/crawlerStore'
import { useCrawlerStatus } from '@/hooks/useCrawler'
import { LanguageSwitch } from './LanguageSwitch'
import { ThemeToggle } from './ThemeToggle'

interface SidebarProps {
  onShowDisclaimer?: () => void
}

const BANNER_DISMISS_KEY = 'mediacrawler_banner_dismissed'

export function Sidebar({ onShowDisclaimer }: SidebarProps) {
  const { t } = useTranslation()
  const { t: tLicense } = useTranslation('license')
  const status = useCrawlerStore((state) => state.status)
  // Banner nhac nho co the tat (khong tat license modal chinh) - nho qua reload.
  // Truoc day khong tat duoc, chiem het chieu rong header tren vien man hinh nho.
  const [bannerDismissed, setBannerDismissed] = useState(
    () => localStorage.getItem(BANNER_DISMISS_KEY) === 'true'
  )

  // Poll status
  useCrawlerStatus()

  const isRunning = status === 'running'

  const dismissBanner = () => {
    localStorage.setItem(BANNER_DISMISS_KEY, 'true')
    setBannerDismissed(true)
  }

  return (
    <header className="min-h-14 flex-shrink-0 glass-panel border-b border-cyber-border-subtle relative z-10">
      <div className="min-h-14 px-4 py-2 flex items-center justify-between gap-3">
        {/* Left: Logo and GitHub Star */}
        <div className="flex items-center gap-3 flex-shrink-0">
          <Bug className="w-5 h-5 text-cyber-neon-cyan" />
          <span className="font-mono font-bold text-cyber-text-primary tracking-wider text-sm">
            MediaCrawler
          </span>
          <a
            href="https://github.com/NanmiCoder/MediaCrawler"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 px-2 py-1 rounded-md border border-cyber-border-subtle hover:border-cyber-neon-cyan hover:shadow-glow-cyan-sm transition-all bg-cyber-bg-tertiary"
          >
            <Github className="w-4 h-4 text-cyber-text-secondary" />
            <span className="text-xs font-mono text-cyber-text-secondary">Star</span>
          </a>
          {isRunning && (
            <Badge variant="running" className="text-[10px]">
              {t('status.active')}
            </Badge>
          )}
          {isRunning && (
            <span className="w-2 h-2 bg-cyber-neon-green rounded-full shadow-glow-green-sm animate-pulse-fast" />
          )}
        </div>

        {/* Center: Warning banner - 1 dong, co the tat; luon con nut nho de mo lai */}
        {!bannerDismissed ? (
          <div className="flex items-center gap-2 min-w-0 flex-1 max-w-xl px-3 py-1.5 rounded-lg border border-cyber-neon-orange/50 bg-cyber-neon-orange/10">
            <button
              onClick={onShowDisclaimer}
              className="flex items-center gap-2 min-w-0 flex-1 text-left cursor-pointer"
              title={`${tLicense('content.line1')} ${tLicense('content.line2')}`}
            >
              <AlertTriangle className="w-4 h-4 text-cyber-neon-orange flex-shrink-0" />
              <span className="text-xs font-mono text-cyber-neon-orange truncate">
                {tLicense('content.line1')} · {tLicense('content.line2')}
              </span>
            </button>
            <button
              onClick={dismissBanner}
              title="Đóng"
              className="flex-shrink-0 p-1 rounded hover:bg-cyber-neon-orange/20 text-cyber-neon-orange"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        ) : (
          <button
            onClick={onShowDisclaimer}
            title="Xem điều khoản sử dụng"
            className="flex-shrink-0 p-1.5 rounded-md hover:bg-cyber-neon-orange/10 text-cyber-neon-orange/60 hover:text-cyber-neon-orange transition-colors"
          >
            <AlertTriangle className="w-4 h-4" />
          </button>
        )}

        {/* Right: Actions and Status */}
        <div className="flex items-center gap-3 flex-shrink-0">
          {/* Theme Toggle */}
          <ThemeToggle />
          {/* Language Switch */}
          <LanguageSwitch />

          {/* Status Info */}
          <div className="hidden lg:flex items-center gap-2 text-xs font-mono">
            <span className="text-cyber-text-muted">{t('sidebar.api')}:</span>
            <span className="text-cyber-neon-green">v1.0.0</span>
            <div className="flex items-center gap-1.5">
              <Wifi className="w-3 h-3 text-cyber-text-secondary" />
              <span className="text-cyber-text-secondary">{t('sidebar.local')}</span>
              <span className="status-dot status-dot-online" />
            </div>
          </div>
        </div>
      </div>
    </header>
  )
}
