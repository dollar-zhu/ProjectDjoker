export type Concept='courtside'|'coach'|'studio';
export function parseConcept(value?:string):Concept{return value==='coach'||value==='studio'?value:'courtside';}
export function designHref(concept:Concept,review:boolean){return `/designs${review?'/serve':''}?concept=${concept}`;}
