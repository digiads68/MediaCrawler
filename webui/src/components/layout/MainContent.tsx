import { Terminal } from '@/components/console/Terminal'
import { useLogWebSocket } from '@/hooks/useWebSocket'

export function MainContent() {
  // Connect to WebSocket for logs
  useLogWebSocket()

  return (
    // min-h dam bao Terminal (chua nut mo Data Explorer / PAYLOAD_MATRIX)
    // khong bao gio bi flexbox ep xuong 0px khi CrawlerConfigPanel cao.
    <main className="flex-1 flex flex-col overflow-hidden min-h-[360px] relative z-10">
      <Terminal />
    </main>
  )
}
