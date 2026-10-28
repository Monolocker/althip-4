// Per-deployer statistics (M20.1)
// Mirrors backend/app/models/deployers.py

export interface QualityCounts {
    tight: number
    wide: number
    unreliable: number
    unknown: number     // no book data yet (sweep pending)
}

export interface DeployerStats {
    venue: string // "" for HL's own markets
    address: string | null
    operatorCount: number
    marketCount: number
    questionCount: number
    volume24h: number
    bookQuality: QualityCounts
    categories: Record<string, number>
    nextEventAt: string | null
    topMarketId: string | null
    topMarketQuestion: string | null
}