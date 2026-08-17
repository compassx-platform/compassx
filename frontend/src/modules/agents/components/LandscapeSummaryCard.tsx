import React from 'react';

export interface LandscapeCategoryItem {
  name: string;
  type: string;
  status: 'fully_available' | 'unregistered' | 'partial' | 'missing';
  details?: string;
}

export interface LandscapeAssessmentProps {
  categories: {
    category_name: string;
    items: LandscapeCategoryItem[];
  }[];
}

export const LandscapeSummaryCard: React.FC<LandscapeAssessmentProps> = ({ categories }) => {
  const getStatusColor = (status: LandscapeCategoryItem['status']) => {
    switch (status) {
      case 'fully_available':
        return '#a6e3a1';
      case 'unregistered':
        return '#89b4fa';
      case 'partial':
        return '#f9e2af';
      case 'missing':
        return '#f38ba8';
      default:
        return '#cdd6f4';
    }
  };

  return (
    <div style={{ margin: '15px 0', padding: '16px', background: '#1e1e2e', border: '1px solid #313244', borderRadius: '8px', color: '#cdd6f4' }}>
      <h4 style={{ margin: '0 0 12px 0', color: '#cba6f7' }}>Landscape & Classification Assessment (E3)</h4>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {categories.map((cat, idx) => (
          <div key={idx} style={{ background: '#181825', padding: '10px 12px', borderRadius: '6px' }}>
            <div style={{ fontWeight: 'bold', marginBottom: '6px', color: '#89b4fa' }}>{cat.category_name}</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {cat.items.map((item, iIdx) => (
                <div key={iIdx} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85em' }}>
                  <span>
                    • {item.name} <span style={{ color: '#6c7086' }}>({item.type})</span>
                  </span>
                  <span style={{ color: getStatusColor(item.status), fontWeight: '600' }}>{item.status.replace('_', ' ')}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
