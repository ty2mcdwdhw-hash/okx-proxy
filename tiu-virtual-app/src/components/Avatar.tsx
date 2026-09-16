export function Avatar({ src, alt }: { src: string; alt: string }) {
  return (
    <div className="avatar">
      <img className="avatar__img" src={src} alt={alt} draggable={false} />
    </div>
  )
}
