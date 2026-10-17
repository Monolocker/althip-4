import { formatTime } from '../utils/format'

interface TimeValueProps {
  value: string | null
}

// One market time, displayed the same way everywhere: UTC first (matching
// titles and resolution rules), the viewer's local time underneath.
function TimeValue({ value }: TimeValueProps) {
  const time = formatTime(value)

  if (time === null) {
    return <>—</>
  }

  return (
    <>
      <span className="time-utc">{time.utc}</span>
      {time.local !== null && (
        <span className="time-local">{time.local}</span>
      )}
    </>
  )
}

export default TimeValue