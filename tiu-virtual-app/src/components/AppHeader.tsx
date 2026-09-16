export function AppHeader({ title, onBack }: { title: string; onBack: () => void }) {
  return (
    <header className="header">
      <button type="button" className="header__back" onClick={onBack} aria-label="Volver">
        <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
          <path
            d="M15.5 3.5 7 12l8.5 8.5"
            fill="none"
            stroke="currentColor"
            strokeWidth="3.4"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>
      <h1 className="header__title">{title}</h1>
    </header>
  )
}
