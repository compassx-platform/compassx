type PageTabItem<TValue extends string> = {
  value: TValue;
  label?: string;
};

type PageTabsProps<TValue extends string> = {
  tabs: readonly PageTabItem<TValue>[];
  value: TValue;
  onChange: (value: TValue) => void;
  className?: string;
  equalWidth?: boolean;
  style?: React.CSSProperties;
};

function defaultLabel(value: string) {
  return value.replace(/[-_]/g, ' ');
}

export function PageTabs<TValue extends string>({
  tabs,
  value,
  onChange,
  className,
  equalWidth,
  style,
}: PageTabsProps<TValue>) {
  return (
    <div
      className={`page-tabs${className ? ` ${className}` : ''}`}
      style={{
        ...(equalWidth ? { display: 'flex', width: '100%', gap: 0 } : {}),
        ...style,
      }}
    >
      {tabs.map((tab) => (
        <button
          key={tab.value}
          type="button"
          className={value === tab.value ? 'is-active' : undefined}
          onClick={() => onChange(tab.value)}
          style={
            equalWidth
              ? {
                  flex: 1,
                  textAlign: 'center',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }
              : undefined
          }
        >
          {tab.label ?? defaultLabel(tab.value)}
        </button>
      ))}
    </div>
  );
}

