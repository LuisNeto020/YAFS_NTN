.. _examples:

========
Examples
========

In this section, we explain the examples in the Examples/ directory, giving you an overview of the more sophisticated implementations. In addition, we invite you to explore the detailed documentation for each example, available at the bottom of this page. This documentation provides more detailed information about the code of each example, helping you to better understand the functionality of each function and its application in the context of the example in question.

* **Tutorial** In main1.py we find the most basic case: allocation in the cloud and minimum path routing. Using this first case, in main2.py we scale the modules in the cloud and use a round robin scheduler. In main3.py, in addition to what was done in the previous one, we show how to implement dynamic control.
* **VRGameFog-IFogSim-WL** This implemention have been used to compare YAFS simulator with iFogSim, implementing a close setup of the experiments.
* **DynamicAllocation** It is a demo of how to implement a dynamic allocation of modules according a customized distribution. We use a random euclidean network from a Graphml format, and several selection, population, and allocation implementations.
* **DynamicFailuresOnNodes** From a euclidean random network we dynamically remove nodes.
* **DynamicWorkload** In this case, we simulate the movement of users in the network. In each step of the customized distribution nodes are allocated in the next node of the path to reach the point on all modules are.
* **ConquestService** Implementation of a solution to the Fog Application Placement Problem (FAPP), based on independent agents that respond to changes in the system based on specific rules.


.. toctree::
   :maxdepth: 1

   Tutorial
   VRGameFog_IFogSim_WL
   DynamicAllocation
   DynamicFailuresOnNodes
   DynamicWorkload
   ConquestService
   
   
   
   