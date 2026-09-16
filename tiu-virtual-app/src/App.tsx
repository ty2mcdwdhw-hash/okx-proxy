import { AppHeader } from './components/AppHeader'
import { Avatar } from './components/Avatar'
import { ClockChip } from './components/ClockChip'
import { IdCard } from './components/IdCard'
import { SkyBackground } from './components/SkyBackground'
import { StatusBar } from './components/StatusBar'
import { config } from './config/card'
import { useNow } from './hooks/useNow'

export default function App() {
  const now = useNow()
  const { student } = config

  const handleBack = () => {
    // No hay pantalla anterior en la demo: el boton solo replica el gesto.
    if (window.history.length > 1) window.history.back()
  }

  return (
    <div className="screen">
      <SkyBackground />

      <div className="screen__content">
        <StatusBar now={now} />
        <AppHeader title={config.title} onBack={handleBack} />
        <ClockChip now={now} />
        <Avatar src={student.photo} alt={`Foto de ${student.firstNames}`} />
        <IdCard student={student} />

        {config.showDemoBadge && (
          <p className="demo-badge">Simulación · app de práctica, sin valor oficial</p>
        )}
      </div>
    </div>
  )
}
