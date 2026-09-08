interface FieldRowProps {
  label: string;
  children: React.ReactNode;
}

export default function FieldRow({ label, children }: FieldRowProps) {
  return (
    <div style={{ marginBottom: 8 }}>
      <label style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)', display: 'block', marginBottom: 3 }}>
        {label}
      </label>
      {children}
    </div>
  );
}
