import { useState } from 'react'
import { useCreateLinks } from '../api/queries'
import { VENUE_NAMES } from '../features/markets/venues'
import type { MatchLevel, Venue } from '../types/venue'

interface LinkConfirmFormProps {
  venue: Venue
  // The outcome-to-market pairs this confirmation would save.
  links: { marketId: string; externalId: string }[]
}

// The "judge and confirm" step shared by suggestions (22.3b) and manual
// linking (22.5): pick a level, write the note a comparable link needs,
// confirm. Extracted when the second caller appeared, so both flows
// enforce decision 2 (22.2) identically.
function LinkConfirmForm({ venue, links }: LinkConfirmFormProps) {
  const [level, setLevel] = useState<MatchLevel>('comparable')
  const [note, setNote] = useState('')
  const create = useCreateLinks()
  const name = VENUE_NAMES[venue]
  const needsNote = level === 'comparable' && note.trim() === ''

  if (create.isSuccess) {
    return (
      <p className="suggestion--done">
        ✓ Linked {create.data.length} {create.data.length === 1 ? 'outcome' : 'outcomes'} on {name}.
      </p>
    )
  }

  return (
    <>
      <fieldset className="suggestion-level">
        <legend>How do the rules compare?</legend>
        <label>
          <input
            type="radio"
            name={`level-${venue}`}
            checked={level === 'comparable'}
            onChange={() => setLevel('comparable')}
          />{' '}
          Comparable: same in the normal case, different at the edges
        </label>
        <label>
          <input
            type="radio"
            name={`level-${venue}`}
            checked={level === 'identical'}
            onChange={() => setLevel('identical')}
          />{' '}
          Identical: same payout in every scenario
        </label>
      </fieldset>

      <label className="suggestion-note">
        Note{' '}
        {level === 'comparable' ? '(required: how do the rules differ?)' : '(optional)'}
        <textarea
          value={note}
          onChange={(event) => setNote(event.target.value)}
          rows={2}
          placeholder="e.g. Cancelled match: Hyperliquid's Draw resolves Yes; this venue resolves No."
        />
      </label>

      {create.isError && (
        <p className="detail-note detail-note--error">{create.error.message}</p>
      )}

      <button
        type="button"
        className="suggestion-confirm"
        disabled={needsNote || create.isPending}
        onClick={() =>
          create.mutate({ venue, matchLevel: level, note: note.trim(), links })
        }
      >
        {create.isPending
          ? 'Confirming…'
          : `Confirm ${links.length} ${links.length === 1 ? 'link' : 'links'} on ${name}`}
      </button>
    </>
  )
}

export default LinkConfirmForm