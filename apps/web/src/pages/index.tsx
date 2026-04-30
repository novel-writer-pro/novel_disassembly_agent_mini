import WorkbenchApp from "@/components/WorkbenchApp";

export default function IndexRoute() {
  return <WorkbenchApp initialWorkspace="library" />;
}

export async function getServerSideProps() {
  return { props: {} };
}
