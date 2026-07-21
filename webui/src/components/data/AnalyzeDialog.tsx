import { useState } from 'react'
import { toast } from 'sonner'
import { BarChart3, FileSpreadsheet, ExternalLink, Loader2, Sparkles } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { kitApi, type KitCommand, type KitAnalyzeResult } from '@/lib/api'
import type { DataFile } from '@/types/crawler'
import axios from 'axios'

interface AnalyzeDialogProps {
  file: DataFile
  open: boolean
  onOpenChange: (open: boolean) => void
}

// 8 case study — nhãn tiếng Việt (tầng DigiAds hướng người dùng VN)
const COMMANDS: { value: KitCommand; label: string; desc: string }[] = [
  { value: 'trend', label: 'Trend Radar (CS1+CS10+CS5)', desc: 'Top bài, format thắng thế, sound đang lên' },
  { value: 'koc', label: 'KOC Scorecard (CS3+CS9)', desc: 'Chấm điểm creator, phát hiện KOC đang lên' },
  { value: 'sov', label: 'Share of Voice (CS11)', desc: 'Thị phần tiếng nói theo brand (cần brand_map)' },
  { value: 'opportunity', label: 'Opportunity Map (CS4/CS6)', desc: 'Bản đồ ngách 4 vùng cơ hội' },
  { value: 'seasonal', label: 'Seasonal Radar (CS7)', desc: 'Đợt sóng mùa vụ theo tuần' },
  { value: 'price', label: 'Price & Promo Intel (CS8)', desc: 'Giá & mồi khuyến mãi đối thủ' },
  { value: 'insight', label: 'Voice of Customer (CS2)', desc: 'Ngân hàng bình luận (cần file comment)' },
  { value: 'angle', label: 'Angle Library (CS5)', desc: 'Xuất angle nạp pipeline AI video' },
]

function isHtml(name: string) {
  return name.toLowerCase().endsWith('.html')
}

export function AnalyzeDialog({ file, open, onOpenChange }: AnalyzeDialogProps) {
  const [command, setCommand] = useState<KitCommand>('trend')
  const [brandMap, setBrandMap] = useState('kit/config/brand_map.json')
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<KitAnalyzeResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const active = COMMANDS.find((c) => c.value === command)!

  const handleRun = async () => {
    setRunning(true)
    setError(null)
    setResult(null)
    try {
      const { data } = await kitApi.analyze({
        command,
        // data API trả path tương đối DATA_DIR; kit cần path tương đối gốc repo
        file: `data/${file.path}`,
        brand_map: command === 'sov' ? brandMap : null,
      })
      setResult(data)
      toast.success(`Phân tích "${command}" xong — ${data.rows} dòng, ${data.reports.length} báo cáo.`)
    } catch (e) {
      let msg = 'Lỗi không xác định.'
      if (axios.isAxiosError(e)) {
        msg = e.response?.data?.detail ?? e.message
      }
      setError(msg)
      toast.error('Phân tích thất bại.')
    } finally {
      setRunning(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[85vh] flex flex-col">
        <DialogHeader className="flex-shrink-0">
          <DialogTitle className="font-mono text-cyber-neon-cyan flex items-center gap-2">
            <Sparkles className="w-4 h-4" />
            Phân tích DigiAds
          </DialogTitle>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto min-h-0 mt-2 space-y-4">
          {/* File nguồn */}
          <div className="text-xs font-mono text-cyber-text-muted">
            Nguồn: <span className="text-cyber-text-secondary">{file.name}</span>
          </div>

          {/* Chọn loại phân tích */}
          <div className="space-y-1.5">
            <label className="text-xs font-mono text-cyber-text-secondary uppercase tracking-wide">
              Loại phân tích
            </label>
            <Select value={command} onValueChange={(v) => setCommand(v as KitCommand)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {COMMANDS.map((c) => (
                  <SelectItem key={c.value} value={c.value} className="font-mono">
                    {c.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-cyber-text-muted font-mono">{active.desc}</p>
          </div>

          {/* brand_map chỉ cho sov */}
          {command === 'sov' && (
            <div className="space-y-1.5">
              <label className="text-xs font-mono text-cyber-text-secondary uppercase tracking-wide">
                Đường dẫn brand_map.json
              </label>
              <Input
                value={brandMap}
                onChange={(e) => setBrandMap(e.target.value)}
                className="font-mono text-xs"
                placeholder="kit/config/brand_map.json"
              />
              <p className="text-xs text-cyber-text-muted font-mono">
                Map brand → từ khoá; tương đối so với gốc dự án.
              </p>
            </div>
          )}

          {/* Nút chạy */}
          <Button
            onClick={handleRun}
            disabled={running}
            className="w-full font-mono"
          >
            {running ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Đang phân tích... (có thể mất 10–60 giây)
              </>
            ) : (
              <>
                <BarChart3 className="w-4 h-4 mr-2" />
                Chạy phân tích
              </>
            )}
          </Button>

          {/* Lỗi */}
          {error && (
            <div className="rounded-md border border-cyber-neon-pink/40 bg-cyber-neon-pink/10 p-3">
              <p className="text-xs font-mono text-cyber-neon-pink break-words">{error}</p>
            </div>
          )}

          {/* Kết quả: danh sách báo cáo */}
          {result && (
            <div className="space-y-2">
              <div className="text-xs font-mono text-cyber-neon-green">
                ✓ {result.rows} dòng · {result.reports.length} file báo cáo
              </div>
              <div className="space-y-1.5">
                {result.reports.map((name) => {
                  const html = isHtml(name)
                  return (
                    <a
                      key={name}
                      href={kitApi.reportUrl(name)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center justify-between gap-3 rounded-md border border-cyber-border-subtle bg-cyber-bg-tertiary px-3 py-2 hover:border-cyber-neon-cyan/50 transition-all group"
                    >
                      <span className="flex items-center gap-2 min-w-0">
                        {html ? (
                          <BarChart3 className="w-4 h-4 text-cyber-neon-cyan flex-shrink-0" />
                        ) : (
                          <FileSpreadsheet className="w-4 h-4 text-cyber-neon-green flex-shrink-0" />
                        )}
                        <span className="font-mono text-xs text-cyber-text-primary truncate">
                          {name}
                        </span>
                      </span>
                      <span className="flex items-center gap-1 text-xs font-mono text-cyber-text-muted group-hover:text-cyber-neon-cyan flex-shrink-0">
                        {html ? 'Mở báo cáo' : 'Tải về'}
                        <ExternalLink className="w-3 h-3" />
                      </span>
                    </a>
                  )
                })}
              </div>
              <p className="text-[11px] text-cyber-text-muted font-mono">
                Báo cáo HTML mở ngay trong tab mới; file Excel tải xuống để chỉnh/gửi khách.
              </p>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
