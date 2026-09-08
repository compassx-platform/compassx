import React from 'react';
import { AssetChip, AssetObjectType } from '../AssetChip';

export const markdownComponents = {
  a: ({ href, children, ...props }: any) => {
    if (href && (href.startsWith('asset://') || href.startsWith('asset:'))) {
      try {
        const raw = href.replace(/^asset:\/\/?/, '');
        const [encodedFullName, search] = raw.split('?');
        const fullName = decodeURIComponent(encodedFullName);
        const params = new URLSearchParams(search || '');
        const objectType = (params.get('type') || 'unknown') as AssetObjectType;
        const displayName =
          typeof children === 'string'
            ? children
            : Array.isArray(children) && typeof children[0] === 'string'
            ? children[0]
            : undefined;

        return (
          <AssetChip
            fullName={fullName}
            objectType={objectType}
            displayName={displayName}
          />
        );
      } catch {
        return <a href={href} {...props}>{children}</a>;
      }
    }
    return (
      <a href={href} target="_blank" rel="noopener noreferrer" {...props}>
        {children}
      </a>
    );
  },
};
export default markdownComponents;
