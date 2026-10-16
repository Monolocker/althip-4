export interface OutcomeSide {
    index: number
    label: string
    coin: string
    price: number | null
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
}

export interface QuestionMembership {
    questionId: string
    name: string
    description: string
    isFallback: boolean
    siblingIds: string[]
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
  }