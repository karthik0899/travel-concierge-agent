import { fmtMoney } from "../steps.js";

function Card({ title, children }) {
  return (
    <div className="rounded-xl border border-line bg-card p-3">
      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
        {title}
      </h4>
      {children}
    </div>
  );
}

const Row = ({ k, v }) => (
  <div className="flex justify-between gap-3 py-0.5 text-xs">
    <span className="text-dim">{k}</span>
    <span className="text-right text-fg">{v}</span>
  </div>
);

// Renders the meaningful slices of a case as cards. Summary first (the recap).
export function Results({ caseData }) {
  const s = caseData?.slices ?? {};
  const cards = [];

  if (s.summary) {
    const sum = s.summary;
    cards.push(
      <Card key="summary" title="Summary">
        <p className="text-sm leading-relaxed text-fg">{sum.narrative}</p>
        {sum.actions_taken?.length > 0 && (
          <ul className="mt-2 list-inside list-disc space-y-0.5 text-xs text-muted">
            {sum.actions_taken.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
        )}
        {sum.next_steps?.length > 0 && (
          <>
            <p className="mt-2 text-[11px] font-semibold uppercase tracking-wide text-dim">
              Next steps
            </p>
            <ul className="mt-1 list-inside list-disc space-y-0.5 text-xs text-muted">
              {sum.next_steps.map((a, i) => (
                <li key={i}>{a}</li>
              ))}
            </ul>
          </>
        )}
      </Card>,
    );
  }

  if (s.identity) {
    const id = s.identity;
    cards.push(
      <Card key="identity" title="Identity">
        <Row k="Verified" v={id.verified ? "✓ yes" : "✗ no"} />
        {id.name && <Row k="Customer" v={id.name} />}
        {id.loyalty_tier && <Row k="Tier" v={id.loyalty_tier} />}
        {id.reason && <Row k="Note" v={id.reason} />}
      </Card>,
    );
  }

  if (s.assessment) {
    const a = s.assessment;
    cards.push(
      <Card key="assessment" title="Assessment">
        <Row k="Type" v={a.confirmed_type} />
        <Row k="Severity" v={a.severity} />
        {a.cause && <Row k="Cause" v={a.cause} />}
        <Row k="Rebooking" v={a.needs_rebooking ? "needed" : "no"} />
        <Row k="Accommodation" v={a.needs_accommodation ? "needed" : "no"} />
      </Card>,
    );
  }

  if (s.rebooking) {
    const r = s.rebooking;
    cards.push(
      <Card key="rebooking" title="Rebooking">
        <Row k="Booked" v={r.booked ? "✓ yes" : "no"} />
        {r.selected && (
          <Row
            k="Flight"
            v={`${r.selected.flight_no} ${r.selected.origin}→${r.selected.destination}`}
          />
        )}
        {r.new_segment_id && <Row k="Segment" v={r.new_segment_id} />}
        {r.reason && <Row k="Note" v={r.reason} />}
      </Card>,
    );
  }

  if (s.accommodation) {
    const h = s.accommodation;
    cards.push(
      <Card key="accommodation" title="Accommodation">
        <Row k="Booked" v={h.booked ? "✓ yes" : "no"} />
        {h.selected && <Row k="Hotel" v={h.selected.name} />}
        {h.confirmation && <Row k="Confirmation" v={h.confirmation} />}
        {h.reason && <Row k="Note" v={h.reason} />}
      </Card>,
    );
  }

  if (s.compensation) {
    const c = s.compensation;
    cards.push(
      <Card key="compensation" title="Compensation">
        <Row k="Eligible" v={c.eligible ? "✓ yes" : "no"} />
        {c.amount && <Row k="Amount" v={fmtMoney(c.amount)} />}
        {c.rule_ref && <Row k="Rule" v={c.rule_ref} />}
        {c.reason && <Row k="Note" v={c.reason} />}
      </Card>,
    );
  }

  if (s.claim) {
    const cl = s.claim;
    cards.push(
      <Card key="claim" title="Claim">
        <Row k="Submitted" v={cl.claim_submitted ? "✓ yes" : "no"} />
        {cl.claim_ref && <Row k="Ref" v={cl.claim_ref} />}
        {cl.status && <Row k="Status" v={cl.status} />}
        {cl.reason && <Row k="Note" v={cl.reason} />}
      </Card>,
    );
  }

  if (!cards.length) {
    return (
      <p className="px-1 py-4 text-center text-xs text-dim">
        Results will appear here as each agent completes.
      </p>
    );
  }
  return <div className="space-y-2">{cards}</div>;
}
