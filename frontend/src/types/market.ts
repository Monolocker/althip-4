export type OutcomeSide = "YES" | "NO"

export interface MarketOutcome {
    side: OutcomeSide
    price: number
}

export interface Market {
    id: string
    question: string
    status: "open" | "closed"
    closesAt: string
    outcomes: MarketOutcome[]
}