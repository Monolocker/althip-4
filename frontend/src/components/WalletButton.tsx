import { useState } from 'react'
import { safeIcon, type WalletInfo } from '../features/wallet/eip1193'
import type { WalletState } from '../features/wallet/useWallet'
import { shortAddress } from '../utils/format'

interface WalletButtonProps {
  wallet: WalletState
  onOpenDashboard: (address: string) => void
}

function WalletIcon({ info }: { info: WalletInfo }) {
  const icon = safeIcon(info.icon)
  return icon === null ? null : <img className="wallet-icon" src={icon} alt="" width={18} height={18} />
}

// Header control (Milestone 27.2): connect a browser wallet to see your
// own account. Read-only: connecting shares the public address, nothing
// is signed and no key leaves the wallet.
function WalletButton({ wallet, onOpenDashboard }: WalletButtonProps) {
  const [picking, setPicking] = useState(false)
  const { wallets, status, address, error } = wallet

  if (status === 'connected' && address !== null && wallet.wallet !== null) {
    return (
      <div className="wallet-control">
        <span className="wallet-account" title={`${address} via ${wallet.wallet.name}`}>
          <WalletIcon info={wallet.wallet} />
          <code>{shortAddress(address)}</code>
        </span>
        <button type="button" onClick={() => onOpenDashboard(address)}>
          My dashboard
        </button>
        <button type="button" className="wallet-secondary" onClick={wallet.disconnect}>
          Disconnect
        </button>
      </div>
    )
  }

  function choose(uuid: string) {
    setPicking(false)
    wallet.connect(uuid)
  }

  return (
    <div className="wallet-control">
      {status === 'connecting' ? (
        <span className="wallet-status">Check your wallet to approve the connection…</span>
      ) : wallets.length === 0 ? (
        <span className="wallet-status">No browser wallet detected</span>
      ) : wallets.length === 1 ? (
        <button type="button" onClick={() => choose(wallets[0].uuid)}>
          Connect {wallets[0].name}
        </button>
      ) : (
        <button type="button" aria-expanded={picking} onClick={() => setPicking(!picking)}>
          Connect wallet
        </button>
      )}
      {picking && status !== 'connecting' && wallets.length > 1 && (
        <ul className="wallet-picker">
          {wallets.map((info) => (
            <li key={info.uuid}>
              <button type="button" onClick={() => choose(info.uuid)}>
                <WalletIcon info={info} />
                {info.name}
              </button>
            </li>
          ))}
        </ul>
      )}
      {error !== null && (
        <p className="wallet-error" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}

export default WalletButton