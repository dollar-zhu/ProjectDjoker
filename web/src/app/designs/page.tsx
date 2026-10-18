import {DesignPrototype} from './prototype';
import {parseConcept} from '@/lib/design-flow';
export default async function Designs({searchParams}:{searchParams:Promise<{concept?:string}>}){
 const query=await searchParams;
 return <DesignPrototype concept={parseConcept(query.concept)} review={false}/>;
}
