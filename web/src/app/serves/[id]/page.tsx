import {notFound} from 'next/navigation';
import {validId} from '@/lib/contracts';
import {ServeWorkspace} from '@/components/serve-workspace';
export default async function Serve({params}:{params:Promise<{id:string}>}){
 const {id}=await params;
 if(!validId(id))notFound();
 return <ServeWorkspace key={id} jobId={id}/>;
}
