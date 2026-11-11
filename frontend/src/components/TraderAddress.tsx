import { useEffect, useState } from 'react'
import { shortAddress } from '../utils/format'

// Hyperliquid's own explorer (listed in the official docs under
// HyperCore tools); /explorer/address/<address> is its address page.
const EXPLORER_URL = 'https://app.hyperliquid.xyz/explorer/address/'
const FEEDBACK_MS = 1500

type CopyState = 'idle' | 'copied' | 'failed'

interface TraderAddressProps {
  address: string
}

// A shortened address with the full one a click away: copy it, or open
// it in Hyperliquid's explorer (Milestone 23.4).
function TraderAddress({ address }: TraderAddressProps) {
  const [copyState, setCopyState] = useState<CopyState>('idle')

  // Back to the plain button after a moment. The cleanup cancels the
  // timer if the row disappears first (for example, the window changes).
  useEffect(() => {
    if (copyState === 'idle') {
      return
    }
    const timerId = window.setTimeout(() => setCopyState('idle'), FEEDBACK_MS)
    return () => window.clearTimeout(timerId)
  }, [copyState])

  async function copy() {
    try {
      // The Clipboard API needs a secure context; localhost counts as one.
      await navigator.clipboard.writeText(address)
      setCopyState('copied')
    } catch {
      setCopyState('failed')
    }
  }

  return (
    <span className="trader-address">
      <code title={address}>{shortAddress(address)}</code>
      <button
        type="button"
        className="trader-address-button"
        aria-label={`Copy address ${address}`}
        onClick={() => void copy()}
      >
        {copyState === 'copied' ? 'Copied' : copyState === 'failed' ? 'Copy failed' : 'Copy'}
      </button>
      <a
        className="trader-address-link"
        href={`${EXPLORER_URL}${address}`}
        target="_blank"
        rel="noopener noreferrer"
      >
        Explorer ↗
      </a>
    </span>
  )
}

export default TraderAddress