import type { StudentCard } from '../config/card'

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="card__field">
      <span className="card__label">{label}</span>
      <span className="card__value">{value}</span>
    </div>
  )
}

export function IdCard({ student }: { student: StudentCard }) {
  return (
    <section className="card">
      <h2 className="card__name">
        <span className="card__name-line">{student.firstNames}</span>
        <span className="card__name-line">{student.lastNames}</span>
      </h2>

      <Field label="Código de alumno:" value={student.studentCode} />
      <Field label="ID Banner:" value={student.bannerId} />

      <p className="card__program">{student.program}</p>
      <p className="card__campus">
        <span className="card__pin" aria-hidden="true">
          📍
        </span>
        {student.campus}
      </p>
    </section>
  )
}
