export function HealthBadge(props: { status: string }): JSX.Element {
  return <span aria-label={`health-${props.status}`}>{props.status}</span>;
}
