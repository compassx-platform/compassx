type PageTabItem<TValue extends string> = {
  value: TValue;
  label?: string;
};

type PageTabsProps<TValue extends string> = {
  tabs: readonly PageTabItem<TValue>[];
  value: TValue;
  onChange: (value: TValue) => void;
  className?: string;
};

function defaultLabel(value: string) {
  return value.replace(/[-_]/g, ' ');
}

export function PageTabs<TValue extends string>({
  tabs,
  value,
  onChange,
  className,
}: PageTabsProps<TValue>) {
  return (
    <div className={`page-tabs${className ? ` ${className}` : ''}`}>
      {tabs.map((tab) => (
        <button
          key={tab.value}
          type="button"
          className={value === tab.value ? 'is-active' : undefined}
          onClick={() => onChange(tab.value)}
        >
          {tab.label ?? defaultLabel(tab.value)}
        </button>
      ))}
    </div>
  );
}
