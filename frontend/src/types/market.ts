export interface OutcomeSide {
    index: number
    label: string
    coin: string
    price: number | null
}

// How much a market's displayed price can be trusted 
// From a background book check minutes old: display only, never for 
// order decisions
export interface BookSummary {
    quality: "tight" | "wide" | "unreliable"
    // "sweep": measured from OB. "mark": inferred bc market
    // has never traded and book check has happened yet
    source: "sweep" | "mark"
    bid: number | null
    ask: number | null
    spread: number | null
    checkedAt: string | null
}

export interface OutcomeMarket {
    id: string
    name: string
    question: string
    description: string
    status: "open" | "settled"
    // When the deciding event is scheduled (price observation time,
    // game start, scheduled decision). Null when the market has none.
    eventAt: string | null
    // Latest expected resolution time. Equal to eventAt for price
    // markets; a later deadline for sports, policy, awards and IPOs.
    resolvesBy: string | null
    quoteToken: string
    venue: string
    sides: OutcomeSide[]
    // Contracts traded in the last 24h, each settles to $1, thus, 
    // this is also total USDC traded across both sides. Null when unknown 
    volume24h: number | null 
    // Null when there is no evidence either way
    book: BookSummary | null
    // "binary": a side's price is a market-implied probability
    // "scalar": proportional payout; prices are not probabilities
    payout: "binary" | "scalar"
}

export interface QuestionMembership {
    questionId: string
    name: string
    description: string
    isFallback: boolean
    siblingIds: string[]
    // Rendered from the question's template; null when unavailable 
    title: string | null
    rules: string | null
}

export interface Settlement {
    settleFraction: number | null
    details: string
    winningSideIndex: number | null
  }
  
  export interface OutcomeMarketDetail extends OutcomeMarket {
    spec: Record<string, string>
    deployer: string | null
    questionGroup: QuestionMembership | null
    settlement: Settlement | null
    // This market's own resolution rules from its template, if any
    rules: string | null
  }