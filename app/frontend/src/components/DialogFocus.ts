import {useEffect,useRef,type RefObject} from 'react';
export function useDialogFocus(root:RefObject<HTMLElement|null>,onClose:()=>void){
 const close=useRef(onClose);close.current=onClose;
 useEffect(()=>{
  const previous=document.activeElement as HTMLElement|null;const overflow=document.body.style.overflow;document.body.style.overflow='hidden';
  const elements=()=>Array.from(root.current?.querySelectorAll<HTMLElement>('button:not(:disabled),a[href],input:not(:disabled),select:not(:disabled),textarea:not(:disabled),[tabindex="0"]')||[]).filter(e=>e.offsetParent!==null);
  elements()[0]?.focus();
  const key=(event:KeyboardEvent)=>{
   if(root.current!==Array.from(document.querySelectorAll('[role="dialog"]')).at(-1))return;
   if(event.key==='Escape'){event.preventDefault();event.stopImmediatePropagation();close.current()}
   if(event.key==='Tab'){const e=elements(),first=e[0],last=e.at(-1);if(!first)return;if(!root.current?.contains(document.activeElement)){event.preventDefault();first.focus()}else if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus()}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus()}}
  };
  document.addEventListener('keydown',key,true);
  return()=>{document.removeEventListener('keydown',key,true);document.body.style.overflow=overflow;if(previous&&document.contains(previous))previous.focus()};
 },[root]);
}
