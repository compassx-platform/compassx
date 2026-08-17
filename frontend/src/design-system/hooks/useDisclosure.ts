import { useCallback, useState } from "react";

export function useDisclosure(defaultOpen = false) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  const open = useCallback(() => setIsOpen(true), []);
  const close = useCallback(() => setIsOpen(false), []);
  const toggle = useCallback(() => setIsOpen((current) => !current), []);

  return { isOpen, open, close, toggle, setIsOpen };
}

