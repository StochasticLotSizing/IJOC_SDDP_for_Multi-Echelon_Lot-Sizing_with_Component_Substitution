from __future__ import absolute_import, division, print_function
import cplex
import math
from Constants import Constants
from SDDPCut import SDDPCut
from ScenarioTree import ScenarioTree
import itertools

# This class contains the attributes and methodss allowing to define one stage of the SDDP algorithm.
class SDDPStage(object):

    def __init__(self, owner=None, previousstage=None, nextstage=None, decisionstage=-1):

        self.SDDPOwner = owner
        self.PreviousSDDPStage = previousstage
        self.NextSDDPStage = nextstage
        self.SDDPCuts = []
        #A Cplex MIP object will be associated to each stage later.
        self.Cplex = cplex.Cplex()
        #The variable MIPDefined is turned to True when the MIP is built
        self.MIPDefined = False
        self.DecisionStage = decisionstage
        self.Instance = self.SDDPOwner.Instance

        #The following attribute will contain the coefficient of hte variable in the cuts
        self.CoefficientConstraint = []
        #The following table constains the value at which the variables are fixed
        self.VariableFixedTo = []
        self.TimePeriodToGo = range(self.DecisionStage, self.Instance.NrTimeBucket)

        self.EVPIScenarioSet = None
        self.EVPIScenarioRange = range(Constants.SDDPNrEVPIScenario)
        #The number of variable of each type in the stage will be set later
        self.NrProductionVariable = 0
        self.NrQuantityVariable = 0
        self.NrConsumptionVariable = 0
        self.NrStockVariable = 0
        self.NrBackOrderVariable = 0
        self.NrEstmateCostToGoPerItemPeriod = 0
        self.NrPIQuantity = 0
        self.NrPIInventory = 0
        self.NrPIBacklog = 0
        self.NrPIConsumption = 0
        self.NrEstmateCostToGoEVPI = 0
        self.ComputeNrVariables()
        #The start of the index of each variable
        self.StartProduction = 0
        self.StartQuantity = self.StartProduction + self.NrProductionVariable
        self.StartConsumption = self.StartQuantity + self.NrQuantityVariable
        self.StartStock = self.StartConsumption + self.NrConsumptionVariable
        self.StartBackOrder = self.StartStock + self.NrStockVariable
        self.StartCostToGo = self.StartBackOrder + self.NrBackOrderVariable
        self.StartEstmateCostToGoPerItemPeriod = self.StartCostToGo + 1
        self.StartPIQuantity = self.StartEstmateCostToGoPerItemPeriod + self.NrEstmateCostToGoPerItemPeriod
        self.StartPIInventory = self.StartPIQuantity + self.NrPIQuantity
        self.StartPIBacklog = self.StartPIInventory + self.NrPIInventory
        self.StartPIConsumption =self.StartPIBacklog + self.NrPIBacklog
        self.StartPICostToGoEVPI = self.StartPIConsumption + self.NrPIConsumption

        #self.StartZ = self.StartEstmateCostToGoPerItemPeriod + self.NrEstmateCostToGoPerItemPeriod
        # Demand and materials requirement: set the value of the invetory level and backorder quantity according to
        #  the quantities produced and the demand
        self.M = cplex.infinity
        self.CurrentTrialNr = -1
        #The quantity to order (filled after having solve the MIPs for all scenario)
        self.QuantityValues = []
        #The value of the production variables (filled after having solve the MIPs for all scenario)
        self.ProductionValue = []
        # The value of the inventory variables (filled after having solve the MIPs for all scenario)
        self.InventoryValue = []
        #The value of the backorder variable (filled after having solve the MIPs for all scenario)
        self.BackorderValue = []
        # The consumption  (filled after having solve the MIPs for all scenario)
        self.ConsumptionValues = []

        # Try to use the corepoint method of papadakos, remove if it doesn't work
        self.CorePointQuantityValues = []
        # The value of the production variables (filled after having solve the MIPs for all scenario)
        self.CorePointProductionValue = []
        # The value of the inventory variables (filled after having solve the MIPs for all scenario)
        self.CorePointInventoryValue = []
        # The value of the backorder variable (filled after having solve the MIPs for all scenario)
        self.CorePointBackorderValue = []

        #The cost of each scenario
        self.StageCostPerScenarioWithoutCostoGo = []
        self.StageCostPerScenarioWithCostoGo = []
        self.PartialCostPerScenario = []
        self.PassCost = -1
        self.NrTrialScenario = -1

        self.LastAddedConstraintIndex = 0
        self.IndexFlowConstraint = []
        self.IndexProductionQuantityConstraint = []
        self.IndexCapacityConstraint = []
        self.IndexCutConstraint = []
        self.IndexConsumptionConstraint = []
        self.ConcernedProductFlowConstraint = []
        self.ConcernedTimeFlowConstraint = []
        self.ConcernedProductProductionQuantityConstraint = []
        self.ConcernedTimeProductionQuantityConstraint = []
        self.ConcernedResourceCapacityConstraint = []
        self.IndexCutConstraint = []
        self.ConcernedCutinConstraint = []

    #Compute the cost of the stage at the current iteration
    def ComputePassCost(self):
        self.PassCost = sum(self.PartialCostPerScenario[w] for w in self.TrialScenarioNrSet) \
                        / self.NrTrialScenario
        self.PassCostWithAproxCosttoGo = sum(self.StageCostPerScenarioWithCostoGo[w]
                                             for w in self.TrialScenarioNrSet) / self.NrTrialScenario

    #This function modify the number of scenario in the stage
    def SetNrTrialScenario(self, nrscenario):
        self.NrTrialScenario = nrscenario
        self.CurrentTrialNr = 0
        self.TrialScenarioNrSet = range(nrscenario)
        #The quantity to order (filled after having solve the MIPs for all scenario)
        self.QuantityValues = [[] for w in self.TrialScenarioNrSet]
        # The quantity to order (filled after having solve the MIPs for all scenario)
        self.ConsumptionValues = [[] for w in self.TrialScenarioNrSet]
        #The value of the production variables (filled after having solve the MIPs for all scenario)
        self.ProductionValue = [[[] for t in self.Instance.TimeBucketSet] for w in self.TrialScenarioNrSet]
        # The value of the inventory variables (filled after having solve the MIPs for all scenario)
        self.InventoryValue = [[] for w in self.TrialScenarioNrSet]
        #The value of the backorder variable (filled after having solve the MIPs for all scenario)
        self.BackorderValue = [[] for w in self.TrialScenarioNrSet]
        # The cost of each scenario
        self.StageCostPerScenarioWithoutCostoGo = [-1 for w in self.TrialScenarioNrSet]
        self.StageCostPerScenarioWithCostoGo = [-1 for w in self.TrialScenarioNrSet]

        self.PartialCostPerScenario = [0 for w in self.TrialScenarioNrSet]

        self.SAAStageCostPerScenarioWithoutCostoGopertrial = [0 for w in self.TrialScenarioNrSet]

        #Return true if the current stage is the last
    def IsLastStage(self):
        return False

    #Return true if the current stage is the first
    def IsFirstStage(self):
        return self.DecisionStage == 0

    #Compute the number of variable of each type (production quantty, setup, inventory, backorder)
    def ComputeNrVariables(self):
        #number of variable at stage 1<t<T
        self.NrBackOrderVariable = len(self.Instance.ProductWithExternalDemand)
        self.NrQuantityVariable = self.Instance.NrProduct
        self.NrConsumptionVariable = len(self.Instance.ConsumptionSet)
        self.NrStockVariable = self.Instance.NrProduct
        self.NrProductionVariable = 0
        self.NrEstmateCostToGoPerItemPeriod = 0
        nrtimeperiodtogo = self.Instance.NrTimeBucket - self.DecisionStage
        if Constants.SDDPUseEVPI:
            self.NrPIQuantity = Constants.SDDPNrEVPIScenario * (nrtimeperiodtogo-1) * self.Instance.NrProduct
            self.NrPIInventory = Constants.SDDPNrEVPIScenario * nrtimeperiodtogo * self.Instance.NrProduct
            self.NrPIBacklog = Constants.SDDPNrEVPIScenario * nrtimeperiodtogo * len(self.Instance.ProductWithExternalDemand)
            self.NrPIConsumption = Constants.SDDPNrEVPIScenario * nrtimeperiodtogo * len(self.Instance.ConsumptionSet)
            self.NrEstmateCostToGoEVPI = 1
       # self.NrZ = 0
        # number of variable at stage 1
        if self.IsFirstStage():
            self.NrProductionVariable = self.Instance.NrTimeBucket * self.Instance.NrProduct
            self.NrBackOrderVariable = 0
            self.NrStockVariable = len(self.Instance.ProductWithoutExternalDemand)
            if Constants.SDDPUseValidInequalities:
                self.NrEstmateCostToGoPerItemPeriod = self.Instance.NrTimeBucket * len(self.Instance.ProductWithExternalDemand)
               # self.NrZ = self.Instance.NrTimeBucket * self.Instance.NrTimeBucket * self.Instance.NrProduct

        # number of variable at stage T
        if self.IsLastStage():
            self.NrQuantityVariable = 0
            self.NrStockVariable = len(self.Instance.ProductWithExternalDemand)

    #return the index of the production variable associated with the product p at time t
    def GetIndexProductionVariable(self, p, t):
        if self.IsFirstStage():
            return self.StartProduction + p*self.Instance.NrTimeBucket + t
        else:
            raise ValueError('Production variables are only defined at stage 0')

        # return the index of the production variable associated with the product p at time t

    def GetIndexPIQuantityVariable(self, p, t, w):
        if self.GetTimePeriodAssociatedToQuantityVariable(p) == t:
            return self.GetIndexQuantityVariable(p)
        else:
            return self.StartPIQuantity + p * (self.Instance.NrTimeBucket-1) * Constants.SDDPNrEVPIScenario \
               + w * (self.Instance.NrTimeBucket-1) \
               + (t-1)

    def GetIndexPIInventoryVariable(self, p, t, w):
        return self.StartPIInventory + p * self.Instance.NrTimeBucket * Constants.SDDPNrEVPIScenario \
                   + w * self.Instance.NrTimeBucket \
                   + t

    def GetIndexPIBacklogVariable(self, p, t, w):
        return self.StartPIBacklog +\
                   self.Instance.ProductWithExternalDemandIndex[p] * self.Instance.NrTimeBucket * Constants.SDDPNrEVPIScenario \
                   + w * self.Instance.NrTimeBucket \
                   + t

    def GetIndexPIConsumptionVariable(self, c, t, w):
        return self.StartPIConsumption + \
               self.Instance.ConsumptionSet.index(c) * self.Instance.NrTimeBucket * Constants.SDDPNrEVPIScenario \
               + w * self.Instance.NrTimeBucket \
               + t

    #return the index of the production variable associated with the product p at time t
    #def GetIndexZVariable(self, p, t, t2):
    #    if self.IsFirstStage():
    #        return self.StartZ + p*self.Instance.NrTimeBucket * self.Instance.NrTimeBucket+ t * self.Instance.NrTimeBucket +t2
    #    else:
    #        raise ValueError('Production variables are only defined at stage 0')

    def GetIndexEstmateCostToGoPerItemPeriod(self, p, t):
        if self.IsFirstStage() and Constants.SDDPUseValidInequalities:
            return self.StartEstmateCostToGoPerItemPeriod + self.Instance.ProductWithExternalDemandIndex[p] * self.Instance.NrTimeBucket + t
        else:
            raise ValueError('EstmateCostToGoPerItemPeriod variables are only defined at stage 0 with valid inequalitties')


    #Return the index of the variable associated with the quanity of product p decided at the current stage
    def GetIndexQuantityVariable(self, p):
        return self.StartQuantity + p

    #Return the index of the variable associated with the quanity of product p decided at the current stage
    def GetIndexConsumptionVariable(self, c):
        return self.StartConsumption + self.Instance.ConsumptionSet.index(c)

    #Return the index of the variable associated with the stock of product p decided at the current stage
    def GetIndexStockVariable(self, p):
        if self.IsLastStage():
            return self.StartStock + self.Instance.ProductWithExternalDemandIndex[p]
        elif self.IsFirstStage():
            return self.StartStock + self.Instance.ProductWithoutExternalDemandIndex[p]
        else:
            return self.StartStock + p

    def GetNamePIStockVariable(self, p, t, w):
            return "PII_%d_%d_%d" % (p, t, w)

    def GetNamePIConsumptionVariable(self, c, t, w):
            return "PIW_%da%dt%ds%d" % (c[0], c[1], t, w)

    def GetNamePIQuantityVariable(self, p, t, w):
            return "PIQ_%d_%d_%d" % (p, t, w)

    def GetNamePIBacklogVariable(self, p, t, w):
        return "PIB_%d_%d_%d" % (p, t, w)

    #Return the index of the variable associated with the stock of product p decided at the current stage
    def GetIndexBackorderVariable(self, p):
        if self.IsFirstStage():
            raise ValueError('Backorder variables are not defined at stage 0')
        else:
            return self.StartBackOrder + self.Instance.ProductWithExternalDemandIndex[p]

    #Return the name of the variable associated with the setup of product p at time t
    def GetNameProductionVariable(self, p, t):
        if self.IsFirstStage():
            return "Y_%d_%d"%(p, t)
        else:
            raise ValueError('Production variables are only defined at stage 0')

    def GetNameEstmateCostToGoPerItemPeriod(self, p, t):
        if self.IsFirstStage() and Constants.SDDPUseValidInequalities:
            return "e_%d_%d"%(p, t)
        else:
            raise ValueError('EstmateCostToGoPerItemPeriod variables are only defined at stage 0 with valid inequalitties')

    # Return the name of the variable associated with the quanity of product p decided at the current stage
    def GetNameQuantityVariable(self, p):
        time = self.GetTimePeriodAssociatedToQuantityVariable(p)
        return "Q_%d_%d"%(p, time)

    # Return the name of the variable associated with the consumption c at the current stage
    def GetNameConsumptionVariable(self, c):
        time = self.GetTimePeriodAssociatedToQuantityVariable(c[1])
        return "W_%da%d_%d"%(c[0], c[1], time)

    # Return the name of the variable associated with the stock of product p decided at the current stage
    def GetNameStockVariable(self, p):
        time = self.GetTimePeriodAssociatedToInventoryVariable(p)
        return "I_%d_%d"%(p, time)

    # Return the name of the variable associated with the backorder of product p decided at the current stage
    def GetNameBackorderVariable(self, p):
         time = self.GetTimePeriodAssociatedToBackorderVariable(p)
         return "B_%d_%d" % (p, time)

    # Return the time period associated with quanity of product p decided at the current stage
    def GetTimePeriodAssociatedToQuantityVariable(self, p):
        result = self.DecisionStage
        return result

    # Return the time period associated with inventory of product p decided at the current stage (the inventory level of component,  at time t is observed at stage t -1 because it is not stochastic)
    def GetTimePeriodAssociatedToInventoryVariable(self, p):
        result = self.DecisionStage - 1
        if not self.Instance.HasExternalDemand[p]:
            result = self.DecisionStage

        return result

    # Return the time period associated with backorder of product p decided at the current stage
    def GetTimePeriodAssociatedToBackorderVariable(self, p):
        result = self.DecisionStage -1
        if not self.Instance.HasExternalDemand[p]:
            raise ValueError('Backorder variables are not defined for component')
        return result

    #This function return the right hand side of flow constraint for product p
    def GetRHSFlowConst(self, p, scenario, forwardpass):
        righthandside = 0
        if self.Instance.HasExternalDemand[p] and not self.IsFirstStage():
            #Demand at period t for item i
            if forwardpass:
                righthandside = righthandside \
                               + self.SDDPOwner.CurrentSetOfTrialScenarios[scenario].Demands[
                                   self.GetTimePeriodAssociatedToInventoryVariable(p)][p]
            else:
                righthandside = righthandside \
                                + self.SDDPOwner.SetOfSAAScenario[scenario].Demands[
                                    self.GetTimePeriodAssociatedToInventoryVariable(p)][p]

            if self.GetTimePeriodAssociatedToBackorderVariable(p) -1 >= 0:
                #Backorder at period t-1
                righthandside = righthandside \
                                   + self.SDDPOwner.GetBackorderFixedEarlier(p,
                                                                             self.GetTimePeriodAssociatedToBackorderVariable(p) - 1,
                                                                             self.CurrentTrialNr)

        productionstartedtime = self.GetTimePeriodAssociatedToInventoryVariable(p) - self.Instance.LeadTimes[p]
        if productionstartedtime >= 0:
            #Production at period t-L_i
            righthandside = righthandside \
                               - self.SDDPOwner.GetQuantityFixedEarlier(p, productionstartedtime,
                                                                        self.CurrentTrialNr)

        if self.GetTimePeriodAssociatedToInventoryVariable(p) - 1 >= -1 and not (self.IsFirstStage() and self.Instance.HasExternalDemand[p] ):
            #inventory at period t- 1
            righthandside = righthandside \
                               - self.SDDPOwner.GetInventoryFixedEarlier(p,
                                                                         self.GetTimePeriodAssociatedToInventoryVariable(
                                                                             p) - 1, self.CurrentTrialNr)
        return righthandside

    #This funciton creates all the flow constraint
    def CreateFlowConstraints(self):
        self.FlowConstraintNR = ["" for p in self.Instance.ProductSet]

        for p in self.Instance.ProductSet:
            if not ((self.IsFirstStage() and self.Instance.HasExternalDemand[p]) or (self.IsLastStage() and (not self.Instance.HasExternalDemand[p]))):
                backordervar = []
                consumptionvar = []
                consumptionvarcoeff = []
                righthandside = [self.GetRHSFlowConst(p, self.CurrentTrialNr, True)]
                if self.Instance.HasExternalDemand[p] and not self.IsFirstStage():
                     backordervar = [self.GetIndexBackorderVariable(p)]

                else:
                     #dependentdemandvar = [self.GetIndexQuantityVariable(q) for q in self.Instance.RequieredProduct[p]]
                     #dependentdemandvarcoeff = [-1 * self.Instance.Requirements[q][p] for q in self.Instance.RequieredProduct[p]]
                     consumptionvar = [self.GetIndexConsumptionVariable(c)
                                        for c in self.Instance.ConsumptionSet if p == c[0]]
                     consumptionvarcoeff = [-1 for c in self.Instance.ConsumptionSet if p == c[0]]

                inventoryvar = [self.GetIndexStockVariable(p)]

                vars = inventoryvar + backordervar + consumptionvar
                coeff = [-1] * len(inventoryvar) \
                        + [1] * len(backordervar) \
                        + consumptionvarcoeff

                if len(vars) > 0:
                       self.Cplex.linear_constraints.add(lin_expr=[cplex.SparsePair(vars, coeff)],
                                                           senses=["E"],
                                                           rhs=righthandside,
                                                           names=["Flow%d" %(p)])
                       self.FlowConstraintNR[p] = "Flow%d" % (p)

                       self.IndexFlowConstraint.append(self.LastAddedConstraintIndex)
                       self.LastAddedConstraintIndex = self.LastAddedConstraintIndex + 1
                       self.ConcernedProductFlowConstraint.append(p)

        # This function creates all the flow constraint

    def CreatePIFlowConstraints(self):

        for w in self.EVPIScenarioRange:
            for t in self.TimePeriodToGo:
                for p in self.Instance.ProductSet:
                    backordervar = []
                    consumptionvar = []
                    consumptionvarcoeff = []
                    righthandside = [self.EVPIScenarioSet[w].Demands[t][p]]

                    qtyvar = []
                    qtycoeff = []
                    if t-self.Instance.LeadTimes[p] >= 0:
                        qtyvar = [self.GetIndexPIQuantityVariable(p, t-self.Instance.LeadTimes[p],w)]
                        qtycoeff = [1.0]

                    if self.Instance.HasExternalDemand[p]:
                        backordervar = [self.GetIndexPIBacklogVariable(p, t, w)]

                    else:
                         consumptionvar = [self.GetIndexPIConsumptionVariable(c, t, w)
                                          for c in self.Instance.ConsumptionSet if p == c[0]]
                         consumptionvarcoeff = [-1 for c in self.Instance.ConsumptionSet if p == c[0]]

                    inventoryvar = [self.GetIndexPIInventoryVariable(p, t, w)]

                    previnventoryvar = []
                    previnventorycoeff = []
                    prevbackordervar = []
                    prevbackordercoeff = []
                    # consider previous inventory and backlogs
                    if t==0:
                        righthandside[0] -= self.Instance.StartingInventories[p]
                    else:
                        previnventoryvar = [self.GetIndexPIInventoryVariable(p, t-1, w)]
                        previnventorycoeff = [1]
                        if self.Instance.HasExternalDemand[p]:
                            prevbackordervar = [self.GetIndexPIBacklogVariable(p, t-1, w)]
                            prevbackordercoeff = [-1]

                    vars = inventoryvar + backordervar + consumptionvar +\
                           previnventoryvar + prevbackordervar + qtyvar
                    coeff = [-1] * len(inventoryvar) \
                            + [1] * len(backordervar) \
                            + consumptionvarcoeff \
                            + previnventorycoeff \
                            + prevbackordercoeff \
                            + qtycoeff


                    if len(vars) > 0:
                        self.Cplex.linear_constraints.add(lin_expr=[cplex.SparsePair(vars, coeff)],
                                                          senses=["E"],
                                                          rhs=righthandside,
                                                          names=["Flow%d" % (p)])

                        self.LastAddedConstraintIndex = self.LastAddedConstraintIndex + 1

    # Return the set of products which are associated with stock decisions at the current stage
    def GetProductWithStockVariable(self):
        result = self.Instance.ProductSet
        # At the first stage, only the components are associated with a stock variable
        if self.IsFirstStage():
            result = self.Instance.ProductWithoutExternalDemand
        #At the last stage only the finish product have inventory variable
        if self.IsLastStage():
            result = self.Instance.ProductWithExternalDemand
        return result

    # Return the set of products which are associated with backorder decisions at the current stage
    def GetProductWithBackOrderVariable(self):
        result = []
        # At each stage except the first, the finsih product are associated with a backorders variable
        if not self.IsFirstStage():
            result = self.Instance.ProductWithExternalDemand
        return result

    #This function returns the right hand side of the production consraint associated with product p
    def GetProductionConstrainRHS(self, p):
        if self.IsFirstStage():
            righthandside = 0.0
        else:
            yvalue = self.SDDPOwner.GetSetupFixedEarlier(p, self.GetTimePeriodAssociatedToQuantityVariable(p),
                                                         self.CurrentTrialNr)
            righthandside = self.GetBigMValue(p) * yvalue

        return righthandside


    # This function creates the  indicator constraint to se the production variable to 1 when a positive quantity is produce
    def CreateProductionConstraints(self):
        for p in self.Instance.ProductSet:
            righthandside = [self.GetProductionConstrainRHS(p)]
            if self.IsFirstStage():
                vars = [self.GetIndexQuantityVariable(p), self.GetIndexProductionVariable(p, self.GetTimePeriodAssociatedToQuantityVariable( p ) ) ]
                coeff = [-1.0, self.GetBigMValue(p)]

                # PrintConstraint( vars, coeff, righthandside )
                self.Cplex.linear_constraints.add(lin_expr=[cplex.SparsePair(vars, coeff)],
                                                  senses=["G"],
                                                  rhs=righthandside)
            else:
                    vars = [self.GetIndexQuantityVariable(p) ]
                    coeff = [1.0]
                    # PrintConstraint( vars, coeff, righthandside )
                    self.Cplex.linear_constraints.add(lin_expr=[cplex.SparsePair(vars, coeff)],
                                                         senses=["L"],
                                                         rhs=righthandside)
            self.IndexProductionQuantityConstraint.append(self.LastAddedConstraintIndex)
            self.LastAddedConstraintIndex = self.LastAddedConstraintIndex + 1

            self.ConcernedProductProductionQuantityConstraint.append(p)
            self.ConcernedTimeProductionQuantityConstraint.append(self.GetTimePeriodAssociatedToQuantityVariable(p))

    def CreatePIProductionConstraints(self):
        for w in self.EVPIScenarioRange:
            for t in self.TimePeriodToGo:
                for p in self.Instance.ProductSet:
                    righthandside = [0.0]
                    vars = [self.GetIndexPIQuantityVariable(p,t, w), self.GetIndexProductionVariable(p, t ) ]
                    coeff = [-1.0, self.GetBigMValue(p)]

                    self.Cplex.linear_constraints.add(lin_expr=[cplex.SparsePair(vars, coeff)],
                                                      senses=["G"],
                                                      rhs=righthandside)
                    self.LastAddedConstraintIndex = self.LastAddedConstraintIndex + 1

    def CreateConsumptionConstraints(self):
        # Capacity constraint
        for p in self.Instance.ProductSet:
            for k in self.Instance.ProductSet:
                if self.Instance.Requirements[p][k] and self.Instance.IsMaterProduct(k):
                    quantityvar = [self.GetIndexQuantityVariable(p)]
                    quantityvarcoeff = [-1.0 * self.Instance.Requirements[p][k]]
                    consumptionvars = []
                    consumptionvarcoeff = []
                    for q in self.Instance.ProductSet:
                        if self.Instance.Alternates[k][q] or k == q:
                            consumptionvars = consumptionvars + [self.GetIndexConsumptionVariable(self.Instance.GetConsumptiontuple(q, p))]
                            consumptionvarcoeff = consumptionvarcoeff + [1.0]
                    righthandside = [0.0]

                    vars = quantityvar + consumptionvars
                    coeff = quantityvarcoeff + consumptionvarcoeff
                    self.Cplex.linear_constraints.add(lin_expr=[cplex.SparsePair(vars, coeff)],
                                                      senses=["E"],
                                                      rhs=righthandside,
                                                      names=["quantityConsumption%d->%d" % (p, k)])
                    self.IndexConsumptionConstraint.append(self.LastAddedConstraintIndex)
                    self.LastAddedConstraintIndex = self.LastAddedConstraintIndex + 1

    def CreatePIConsumptionConstraints(self):
        # Capacity constraint
        for w in self.EVPIScenarioRange:
            for t in self.Instance.TimeBucketSet:
                for p in self.Instance.ProductSet:
                    for k in self.Instance.ProductSet:
                        if self.Instance.Requirements[p][k] and self.Instance.IsMaterProduct(k):
                            quantityvar = [self.GetIndexPIQuantityVariable(p, t, w)]
                            quantityvarcoeff = [-1.0 * self.Instance.Requirements[p][k]]
                            consumptionvars = []
                            consumptionvarcoeff = []
                            for q in self.Instance.ProductSet:
                                if self.Instance.Alternates[k][q] or k == q:
                                    consumptionvars = consumptionvars + [self.GetIndexPIConsumptionVariable(self.Instance.GetConsumptiontuple(q, p), t, w)]
                                    consumptionvarcoeff = consumptionvarcoeff + [1.0]
                            righthandside = [0.0]

                            vars = quantityvar + consumptionvars
                            coeff = quantityvarcoeff + consumptionvarcoeff
                            self.Cplex.linear_constraints.add(lin_expr=[cplex.SparsePair(vars, coeff)],
                                                              senses=["E"],
                                                              rhs=righthandside,
                                                              names=["quantityPIConsumption%d->%d" % (p, k)])
                            self.LastAddedConstraintIndex = self.LastAddedConstraintIndex + 1


    def CreateCapacityConstraints(self):
        # Capacity constraint
        if self.Instance.NrResource > 0 and not self.IsLastStage():
            for k in range(self.Instance.NrResource):
               vars = [self.GetIndexQuantityVariable(p) for p in self.Instance.ProductSet]
               coeff = [float(self.Instance.ProcessingTime[p][k]) for p in self.Instance.ProductSet]
               righthandside = [float(self.Instance.Capacity[k])]

               self.Cplex.linear_constraints.add(lin_expr=[cplex.SparsePair(vars, coeff)],
                                                  senses=["L"],
                                                  rhs=righthandside)

               self.IndexCapacityConstraint.append(self.LastAddedConstraintIndex)
               self.LastAddedConstraintIndex = self.LastAddedConstraintIndex + 1

               self.ConcernedResourceCapacityConstraint.append(k)

    def CreatePICapacityConstraints(self):
        # Capacity constraint
        if self.Instance.NrResource > 0 and not self.IsLastStage():
            for t in self.TimePeriodToGo:
                for w in self.EVPIScenarioRange:
                    for k in range(self.Instance.NrResource):
                        vars = [self.GetIndexPIQuantityVariable(p, t, w) for p in self.Instance.ProductSet]
                        coeff = [float(self.Instance.ProcessingTime[p][k]) for p in self.Instance.ProductSet]
                        righthandside = [float(self.Instance.Capacity[k])]

                        self.Cplex.linear_constraints.add(lin_expr=[cplex.SparsePair(vars, coeff)],
                                                          senses=["L"],
                                                          rhs=righthandside)

                        self.LastAddedConstraintIndex = self.LastAddedConstraintIndex + 1

    def CreatePIEstiamteEVPIConstraints(self):

        var = [self.GetIndexPIQuantityVariable(p, t, w)
                     for p in self.Instance.ProductSet
                     for t in range(1, self.Instance.NrTimeBucket)
                     for w in self.EVPIScenarioRange]

        coeff = [w.Probability
                         * math.pow(self.Instance.Gamma, t)
                         * self.Instance.VariableCost[p]
                         for p in self.Instance.ProductSet
                         for t in range(1, self.Instance.NrTimeBucket)
                         for w in self.EVPIScenarioSet]

        var = var + [self.GetIndexPIConsumptionVariable(c, t, w)
                     for c in self.Instance.ConsumptionSet
                     for t in range(1, self.Instance.NrTimeBucket)
                     for w in self.EVPIScenarioRange]

        coeff = coeff + [w.Probability
                         * math.pow(self.Instance.Gamma, t)
                         * self.Instance.AternateCosts[c[1]][c[0]]
                         for c in self.Instance.ConsumptionSet
                         for t in range(1, self.Instance.NrTimeBucket)
                         for w in self.EVPIScenarioSet]


        var = var + [self.GetIndexPIInventoryVariable(p, t, w)
                     for p in self.Instance.ProductSet
                     for t in self.Instance.TimeBucketSet
                     for w in self.EVPIScenarioRange]

        coeff = coeff + [w.Probability
                         * math.pow(self.Instance.Gamma, t)
                         * self.Instance.InventoryCosts[p]
                         if t > self.GetTimePeriodAssociatedToInventoryVariable(p)
                         else 0.0
                         for p in self.Instance.ProductSet
                         for t in self.Instance.TimeBucketSet
                         for w in self.EVPIScenarioSet]

        var = var + [self.GetIndexPIBacklogVariable(p, t, w)
                     for p in self.Instance.ProductWithExternalDemand
                     for t in self.Instance.TimeBucketSet
                     for w in self.EVPIScenarioRange]

        coeff = coeff + [self.GetBacklogCost(p,t,w)
                         if t > self.GetTimePeriodAssociatedToBackorderVariable(p)
                         else 0.0
                         for p in self.Instance.ProductWithExternalDemand
                         for t in self.Instance.TimeBucketSet
                         for w in self.EVPIScenarioSet]

        var = var + [self.StartPICostToGoEVPI]

        coeff = coeff + [-1.0]

        self.Cplex.linear_constraints.add(lin_expr=[cplex.SparsePair(var, coeff)],
                                          senses=["E"],
                                          rhs=[0.0])
        self.LastAddedConstraintIndex = self.LastAddedConstraintIndex + 1

        var = [self.StartPICostToGoEVPI, self.StartCostToGo]
        coeff = [-1.0, 1.0]

        self.Cplex.linear_constraints.add(lin_expr=[cplex.SparsePair(var, coeff)],
                                          senses=["G"],
                                          rhs=[0.0])
        self.LastAddedConstraintIndex = self.LastAddedConstraintIndex + 1

    def GetBacklogCost(self, p, t, w):
        if t == self.Instance.NrTimeBucket-1:
            result = w.Probability \
                     * math.pow(self.Instance.Gamma, t) \
                     * self.Instance.LostSaleCost[p]
        else:
            result = w.Probability \
                    * math.pow(self.Instance.Gamma, t) \
                    * self.Instance.BackorderCosts[p]

        return result

    #Define the variables
    def DefineVariables(self):
        #The setups are decided at the first stage
        if self.IsFirstStage():
            if Constants.SolveRelaxationFirst:
                self.Cplex.variables.add(obj=[math.pow(self.Instance.Gamma, t)
                                                       * self.Instance.SetupCosts[p]
                                                        for p in self.Instance.ProductSet
                                                        for t in self.Instance.TimeBucketSet],
                                                        lb=[0.0] * self.NrProductionVariable,
                                                        ub=[1.0] * self.NrProductionVariable)
                                                    #types=['B'] * self.NrProductionVariable)
            else:
                self.Cplex.variables.add(obj=[math.pow(self.Instance.Gamma, t)
                                              * self.Instance.SetupCosts[p]
                                              for p in self.Instance.ProductSet
                                              for t in self.Instance.TimeBucketSet],
                                         types=['B'] * self.NrProductionVariable)


        #Variable for the production quanitity
        self.Cplex.variables.add(obj=[math.pow(self.Instance.Gamma, self.DecisionStage - 1)
                                      * self.Instance.VariableCost[p]
                                      for p in self.Instance.ProductSet],
                                 lb=[0.0] * self.NrQuantityVariable,
                                 ub=[self.M] * self.NrQuantityVariable)

        #Variable for the consumption
        self.Cplex.variables.add(obj=[math.pow(self.Instance.Gamma, self.DecisionStage - 1)
                                      * self.Instance.AternateCosts[c[1]][c[0]]
                                      for c in self.Instance.ConsumptionSet],
                                 lb=[0.0] * self.NrConsumptionVariable,
                                 ub=[self.M] * self.NrConsumptionVariable)

        #Variable for the inventory
        productwithstockvariable = self.GetProductWithStockVariable()
        self.Cplex.variables.add(obj=[math.pow(self.Instance.Gamma, self.DecisionStage-1)
                                      * self.Instance.InventoryCosts[p]
                                      if self.Instance.HasExternalDemand[p]
                                      else math.pow(self.Instance.Gamma, self.DecisionStage)
                                           * self.Instance.InventoryCosts[p]
                                      for p in productwithstockvariable],
                                  lb=[0.0] * len(productwithstockvariable),
                                  ub=[self.M] * len(productwithstockvariable))

        # Backorder/lostsales variables
        productwithbackorder= self.GetProductWithBackOrderVariable()
        self.Cplex.variables.add(obj=[math.pow(self.Instance.Gamma, self.DecisionStage - 1) * self.Instance.BackorderCosts[p]
                                      if not self.IsLastStage()
                                      else math.pow(self.Instance.Gamma, self.DecisionStage -1) * self.Instance.LostSaleCost[p]
                                      for p in productwithbackorder],
                                      lb=[0.0] * self.NrBackOrderVariable,
                                      ub=[self.M] * self.NrBackOrderVariable)

        if not self.IsLastStage():
            self.Cplex.variables.add(obj=[1], lb=[0.0], ub=[self.M])

        if Constants.SDDPUseValidInequalities:
            self.Cplex.variables.add(obj=[0.0] * self.NrEstmateCostToGoPerItemPeriod,
                                     lb=[0.0] * self.NrEstmateCostToGoPerItemPeriod,
                                     ub=[self.M] * self.NrEstmateCostToGoPerItemPeriod)

        if self.IsFirstStage() and Constants.SDDPUseEVPI:
             self.Cplex.variables.add(obj=[0.0] * self.NrPIQuantity,
                                      lb=[0.0] * self.NrPIQuantity,
                                      ub=[self.M] * self.NrPIQuantity)
             self.Cplex.variables.add(obj=[0.0] * self.NrPIInventory,
                                     lb=[0.0] * self.NrPIInventory,
                                     ub=[self.M] * self.NrPIInventory)
             self.Cplex.variables.add(obj=[0.0] * self.NrPIBacklog,
                                     lb=[0.0] * self.NrPIBacklog,
                                     ub=[self.M] * self.NrPIBacklog)
             #self.M] * self.NrPIBacklog)
             self.Cplex.variables.add(obj=[0.0] * self.NrPIConsumption,
                                     lb=[0.0] * self.NrPIConsumption,
                                     ub=[self.M] * self.NrPIConsumption)
             self.Cplex.variables.add(obj=[0.0] * self.NrEstmateCostToGoEVPI,
                                     lb=[0.0] * self.NrEstmateCostToGoEVPI,
                                     ub=[self.M] * self.NrEstmateCostToGoEVPI)


        #In debug mode, the variables have names
        if Constants.Debug:
            self.AddVariableName()

    #Add the name of each variable
    def AddVariableName(self):
        if Constants.Debug:
            print("Add the names of the variable")
        # Define the variable name.
        # Usefull for debuging purpose. Otherwise, disable it, it is time consuming.
        if Constants.Debug:
            quantityvars = []
            consumptionvars = []
            inventoryvars = []
            productionvars = []
            backordervars = []
            if self.IsFirstStage():
                for p in self.Instance.ProductSet:
                    for t in self.Instance.TimeBucketSet:
                        productionvars.append((self.GetIndexProductionVariable(p, t), self.GetNameProductionVariable(p, t)))

            productwithstockvariable = self.GetProductWithStockVariable()
            for p in productwithstockvariable:
                inventoryvars.append((self.GetIndexStockVariable(p), self.GetNameStockVariable(p)))

            for p in self.GetProductWithBackOrderVariable():
                backordervars.append((self.GetIndexBackorderVariable(p), self.GetNameBackorderVariable(p)))

            for p in self.Instance.ProductSet:
                quantityvars.append((self.GetIndexQuantityVariable(p), self.GetNameQuantityVariable(p)))

            for c in self.Instance.ConsumptionSet:
                consumptionvars.append((self.GetIndexConsumptionVariable(c), self.GetNameConsumptionVariable(c)))

            costtogoperperioditemvars = []
            if self.IsFirstStage() and Constants.SDDPUseValidInequalities:
                for p in self.Instance.ProductWithExternalDemand:
                    for t in self.Instance.TimeBucketSet:
                         costtogoperperioditemvars.append((self.GetIndexEstmateCostToGoPerItemPeriod(p,t),
                                                           self.GetNameEstmateCostToGoPerItemPeriod(p,t)))

            costtogovars = [(self.StartCostToGo, "E%d"%(self.DecisionStage + 1))]

            piquantityvar = []
            pibacklogvar = []
            pistockvar = []
            piconsumptionvar = []
            picosttogovar = []
            if self.IsFirstStage() and Constants.SDDPUseEVPI:
                for w in self.EVPIScenarioRange:
                    for t in self.Instance.TimeBucketSet:
                        for p in self.Instance.ProductSet:
                            if t<> self.GetTimePeriodAssociatedToQuantityVariable(p):
                                piquantityvar.append((self.GetIndexPIQuantityVariable(p,t,w),
                                                      self.GetNamePIQuantityVariable(p,t,w)))
                            pistockvar.append((self.GetIndexPIInventoryVariable(p,t,w),
                                                      self.GetNamePIStockVariable(p,t,w)))
                            if self.Instance.HasExternalDemand[p]:
                                pibacklogvar.append((self.GetIndexPIBacklogVariable(p, t, w),
                                                    self.GetNamePIBacklogVariable(p, t, w)))
                        for c in self.Instance.ConsumptionSet:
                            piconsumptionvar.append((self.GetIndexPIConsumptionVariable(c, t, w),
                                                    self.GetNamePIConsumptionVariable(c,t,w)))
                picosttogovar = [(self.StartPICostToGoEVPI, "evpi_cost_to_go")]

            quantityvars = list(set(quantityvars))
            consumptionvars = list(set(consumptionvars))
            productionvars = list(set(productionvars))
            inventoryvars = list(set(inventoryvars))
            backordervars = list(set(backordervars))
            costtogovars = list(set(costtogovars))
            costtogoperperioditemvars = list(set(costtogoperperioditemvars))
            piquantityvar = list(set(piquantityvar))
            pibacklogvar = list(set(pibacklogvar))
            pistockvar = list(set(pistockvar))
            piconsumptionvar = list(set(piconsumptionvar))
            picosttogovar = list(set(picosttogovar))

            varnames = quantityvars + consumptionvars + inventoryvars +\
                       productionvars + backordervars + costtogovars + \
                       costtogoperperioditemvars +\
                       piquantityvar + pibacklogvar + pistockvar + piconsumptionvar + \
                       picosttogovar
            self.Cplex.variables.set_names(varnames)


    #Create the MIP
    def DefineMIP(self, scenarionr):
        if Constants.Debug:
            print("Define the MIP of stage %d" % self.DecisionStage)
        self.DefineVariables()
        self.CurrentTrialNr = scenarionr

        if not self.IsLastStage():
            self.CreateProductionConstraints()
            self.CreateConsumptionConstraints()
            self.CreateCapacityConstraints()

            for c in self.SDDPCuts:
                c.AddCut()

        self.CreateFlowConstraints()

        if self.IsFirstStage() and Constants.SDDPUseValidInequalities:
            self.CreateValideInequalities()

        if self.IsFirstStage() and Constants.SDDPUseEVPI:
            self.EVPIScenarioSet = self.SDDPOwner.GenerateScenarios(Constants.SDDPNrEVPIScenario, average=True)

            # set the demand to the average of the sample
            scenario = self.EVPIScenarioSet[0]
            for t in self.Instance.TimeBucketSet:
                for p in self.Instance.ProductWithExternalDemand:
                    scenario.Demands[t][p] = sum(w.Demands[t][p] for w in self.SDDPOwner.SetOfSAAScenario) \
                                             / self.SDDPOwner.NrScenarioSAA

            self.CreatePIFlowConstraints()
            #self.CreatePICapacityConstraints()
            self.CreatePIConsumptionConstraints()
            self.CreatePIProductionConstraints()
            self.CreatePIEstiamteEVPIConstraints()

        self.MIPDefined = True

    #The function below update the constraint of the MIP to correspond to the new scenario
    def UpdateMIPForScenarioAndTrialSolution(self, scenarionr, trial, forward):
        self.CurrentTrialNr = trial
        constraintuples = []

        for i in range(len(self.IndexFlowConstraint)):
            constr = self.IndexFlowConstraint[i]
            p = self.ConcernedProductFlowConstraint[i]
            rhs = self.GetRHSFlowConst(p, scenarionr, forward)
            #else:
            #    t = self.ConcernedTimeFlowConstraint[i]
            #    rhs = self.GetRHSFlowConst(p, t)
            constraintuples.append((constr, rhs))


        for cut in self.SDDPCuts:
            # Do not modify a cut that is not already added
            if cut.IsActive:
                constraintuples.append(cut.ModifyCut())


        if len(constraintuples) > 0:
            self.Cplex.linear_constraints.set_rhs(constraintuples)


    #This function update the MIP for the current stage, taking into account the new value fixedin the previous stage
    def UpdateMIPForStage(self):
        #if not self.IsFirstStage():
            constraintuples =[]
           # for i in range(len(self.IndexProductionQuantityConstraint)):
           #         constr = self.IndexProductionQuantityConstraint[i]
           #         p = self.ConcernedProductProductionQuantityConstraint[i]
           #         if not self.IsLastStage():
           #             rhs = self.GetProductionConstrainRHS(p)
           #         else:
           #             t = self.ConcernedTimeProductionQuantityConstraint[i]
           #             rhs= self.GetProductionConstrainRHS(p,t)

           #         constraintuples.append((constr, rhs))

            for i in range(len(self.IndexProductionQuantityConstraint)):
                constr = self.IndexProductionQuantityConstraint[i]
                p = self.ConcernedProductProductionQuantityConstraint[i]
                rhs = self.GetProductionConstrainRHS(p)

                constraintuples.append((constr, rhs))

                # self.Cplex.linear_constraints.set_rhs(constraintuples)

                # constrainttuples = []

            if len(constraintuples) > 0:
                # print constraintuples
                self.Cplex.linear_constraints.set_rhs(constraintuples)



    #This run the MIP of the current stage (one for each scenario)
    def RunForwardPassMIP(self):

        generatecut = False #self.IsLastStage() and not self.SDDPOwner.EvaluationMode \
                      #and (self.SDDPOwner.UseCorePoint or not Constants.GenerateStrongCut)



        if Constants.Debug:
            print("build the MIP of stage %d" %self.DecisionStage)

        # Create a cute for the previous stage problem
        if generatecut:
            cut = SDDPCut(self.PreviousSDDPStage)

        averagecostofthesubproblem = 0

        if self.MIPDefined:
            self.UpdateMIPForStage()

        if self.IsFirstStage():
            consideredscenario = [0]#range( len( self.SDDPOwner.CurrentSetOfScenarios ) )
        else:
            consideredscenario = range(len(self.SDDPOwner.CurrentSetOfTrialScenarios))

        for w in consideredscenario:
            if not self.MIPDefined:
                self.DefineMIP(w)
            else:
                self.UpdateMIPForScenarioAndTrialSolution(w, w, True)
            if Constants.SDDPPrintDebugLPFiles : #or self.IsFirstStage():
                print("Update or build the MIP of stage %d for scenario %d" %(self.DecisionStage, w))
                self.Cplex.write("./Temp/stage_%d_iter_%d_scenar_%d.lp" % (self.DecisionStage, self.SDDPOwner.CurrentIteration, w))
            else:
                # name = "mrp_log%r_%r_%r" % ( self.Instance.InstanceName, self.Model, self.DemandScenarioTree.Seed )
                if not Constants.Debug:
                    self.Cplex.set_log_stream(None)
                    self.Cplex.set_results_stream(None)
                    self.Cplex.set_warning_stream(None)
                    self.Cplex.set_error_stream(None)
            self.Cplex.parameters.advance = 1
            self.Cplex.parameters.lpmethod = 2  # Dual primal cplex.CPX_ALG_DUAL
            self.Cplex.parameters.threads.set(1)
            self.Cplex.solve()
            if Constants.Debug:
                 print("Solution status:%r"%self.Cplex.solution.get_status())

            if self.IsFirstStage():
                self.CurrentTrialNr = 0
                self.SaveSolutionForScenario()
                self.CopyDecisionOfScenario0ToAllScenario()
            else:
                self.SaveSolutionForScenario()

            averagecostofthesubproblem += self.Cplex.solution.get_objective_value() \
                                          * self.SDDPOwner.CurrentSetOfTrialScenarios[w].Probability

            #update the last iteration where dual were used
            if Constants.SDDPCleanCuts and not self.IsLastStage() and len(self.IndexCutConstraint)>0:
                sol = self.Cplex.solution
                duals = sol.get_linear_slacks(self.IndexCutConstraint)
                #print("cut slack %s"%duals)
                for i in range(len(duals)):
                    if duals[i] <> 0:
                        c = self.ConcernedCutinConstraint[i]
                        c.LastIterationWithDual = self.SDDPOwner.CurrentIteration


            if generatecut:
                sol = self.Cplex.solution
                if Constants.SDDPPrintDebugLPFiles:
                    sol.write("./Temp/bacward_mrpsolutionstage_%d_iter_%d_scenar_%d.sol" % (self.DecisionStage, self.SDDPOwner.CurrentIteration, w))
                self.ImproveCutFromSolution(cut, sol)
                #print("Cut RHS after scenario %s"%cut.GetRHS())
        if generatecut:
                # Average by the number of scenario
            cut.UpdateRHS()#float(len(self.SDDPOwner.CurrentSetOfScenarios)))
            if Constants.Debug:
                self.checknewcut(cut, averagecostofthesubproblem, self.PreviousSDDPStage.Cplex.solution)

            cut.AddCut()

        #if self.IsLastStage():
            # Average by the number of scenario
        #    cut.DivideAllCoeff(len(self.SDDPOwner.CurrentSetOfScenarios))

    def CopyDecisionOfScenario0ToAllScenario(self):
        for w2 in range(1, len(self.SDDPOwner.CurrentSetOfTrialScenarios)):
            self.CurrentTrialNr = w2
            self.StageCostPerScenarioWithCostoGo[self.CurrentTrialNr] = self.StageCostPerScenarioWithCostoGo[0]
            self.PartialCostPerScenario[self.CurrentTrialNr] = self.PartialCostPerScenario[0]
            self.QuantityValues[self.CurrentTrialNr] = self.QuantityValues[0]
            self.ConsumptionValues[self.CurrentTrialNr] = self.ConsumptionValues[0]
            self.ProductionValue[self.CurrentTrialNr] = self.ProductionValue[0]
            self.InventoryValue[self.CurrentTrialNr] = self.InventoryValue[0]
            self.BackorderValue[self.CurrentTrialNr] = self.BackorderValue[0]

    def GetVariableValue(self, sol):
        indexarray = [self.GetIndexQuantityVariable(p) for p in self.Instance.ProductSet]
        self.QuantityValues[self.CurrentTrialNr] = sol.get_values(indexarray)

        indexarray = [self.GetIndexConsumptionVariable(c) for c in self.Instance.ConsumptionSet]
        self.ConsumptionValues[self.CurrentTrialNr] = sol.get_values(indexarray)

        if self.IsFirstStage():
            indexarray = [self.GetIndexProductionVariable(p, t) for t in self.Instance.TimeBucketSet
                          for p in self.Instance.ProductSet]
            values = sol.get_values(indexarray)
            self.ProductionValue[self.CurrentTrialNr] = [[max(values[t * self.Instance.NrProduct + p], 0.0)
                                                          for p in self.Instance.ProductSet]
                                                         for t in self.Instance.TimeBucketSet]
                #[round( values[t * self.Instance.NrProduct + p], 0) for p in self.Instance.ProductSet] for t in
                #self.Instance.TimeBucketSet]

        prductwithstock = self.GetProductWithStockVariable()
        indexarray = [self.GetIndexStockVariable(p) for p in prductwithstock]
        inventory = sol.get_values(indexarray)
        if self.IsFirstStage():
            self.InventoryValue[self.CurrentTrialNr] = ['nan' for p in self.Instance.ProductSet]
            index = 0
            for p in prductwithstock:
                self.InventoryValue[self.CurrentTrialNr][p] = inventory[index]
                index = index + 1
        else:
           self.InventoryValue[self.CurrentTrialNr] = inventory

        if not self.IsFirstStage():
            indexarray = [self.GetIndexBackorderVariable(p) for p in self.GetProductWithBackOrderVariable()]
            self.BackorderValue[self.CurrentTrialNr] = sol.get_values(indexarray)


    # This function run the MIP of the current stage
    def SaveSolutionForScenario(self):

        sol = self.Cplex.solution
        if sol.is_primal_feasible():
            if Constants.SDDPPrintDebugLPFiles:
                sol.write("./Temp/mrpsolution.sol")
            self.SaveSolutionFromSol(sol)
        else:
            self.Cplex.write("InfeasibleLP_stage_%d_iter_%d_scenar_%d.lp" % (
            self.DecisionStage, self.SDDPOwner.CurrentIteration, self.CurrentTrialNr))
            raise NameError("Infeasible sub-problem!!!!")

    def SaveSolutionFromSol(self, sol):
            obj = sol.get_objective_value()

            self.StageCostPerScenarioWithCostoGo[self.CurrentTrialNr] = obj
            self.StageCostPerScenarioWithoutCostoGo[self.CurrentTrialNr] = self.StageCostPerScenarioWithCostoGo[self.CurrentTrialNr]

            if not self.IsLastStage():
                self.StageCostPerScenarioWithoutCostoGo[self.CurrentTrialNr] = self.StageCostPerScenarioWithCostoGo[self.CurrentTrialNr] - sol.get_values([self.StartCostToGo])[0]

            if self.IsFirstStage():
                self.PartialCostPerScenario[self.CurrentTrialNr] = self.StageCostPerScenarioWithoutCostoGo[self.CurrentTrialNr]
            else:
                self.PartialCostPerScenario[self.CurrentTrialNr] = self.StageCostPerScenarioWithoutCostoGo[self.CurrentTrialNr] \
                                                                   + self.PreviousSDDPStage.PartialCostPerScenario[self.CurrentTrialNr]
            self.GetVariableValue(sol)

            if Constants.Debug:
                cotogo = 0
                if not self.IsLastStage():
                    cotogo = sol.get_values([self.StartCostToGo])[0]

                print("******************** Solution at stage %d cost: %r cost to go %r *********************"
                      %(self.DecisionStage, sol.get_objective_value(),cotogo))
                print(" Quantities: %r"%self.QuantityValues)
                print(" Inventory: %r"%self.InventoryValue)
                print(" BackOrder: %r"%self.BackorderValue)
                if self.IsFirstStage():
                    print(" Production: %r "%self.ProductionValue)
                print("*************************************************************")


    def ImproveCutFromSolution(self, cut, solution, scenario):
        self.IncreaseCutWithFlowDual(cut, solution, scenario)


        if not self.IsLastStage():
            self.IncreaseCutWithProductionDual(cut, solution, scenario)
            self.IncreaseCutWithCapacityDual(cut, solution, scenario)
            self.IncreaseCutWithCutDuals(cut, solution, scenario)

    #Generate the bender cut
    def GernerateCut(self, trial, returncut=False):
        if Constants.Debug:
            print("Generate a cut to add at stage %d" % self.PreviousSDDPStage.DecisionStage)


        if  not self.IsFirstStage():
            # Re-run the MIP to take into account the just added cut
            # Solve the problem for each scenario
            self.UpdateMIPForStage()

            cutsets = []
            avgcostssubprob = []
            for trial in self.SDDPOwner.ConsideredTrialForBackward:#:
                self.SAAStageCostPerScenarioWithoutCostoGopertrial[trial] = 0
                self.CurrentTrialNr = trial
                # Create a cute for the previous stage problem
                cut = SDDPCut(self.PreviousSDDPStage, trial)
                averagecostofthesubproblem = 0
                for scenario in self.SDDPOwner.SAAScenarioNrSet:
                    self.UpdateMIPForScenarioAndTrialSolution(scenario, trial, False)
                    if Constants.SDDPPrintDebugLPFiles:
                        print("Resolve for backward pass the MIP of stage %d for scenario %d" % (self.DecisionStage, scenario))
                        self.Cplex.write("./Temp/backward_stage_%d_iter_%d_scenar_%d.lp"
                                         % (self.DecisionStage, self.SDDPOwner.CurrentIteration, scenario))

                    self.Cplex.parameters.threads.set(1)
                    self.Cplex.solve()


                    sol = self.Cplex.solution



                    if Constants.Debug:
                        print("cost of subproblem: %r"%sol.get_objective_value())
                    averagecostofthesubproblem += sol.get_objective_value() \
                                                  * self.SDDPOwner.SetOfSAAScenario[scenario].Probability

                    if not self.IsLastStage():
                        self.SAAStageCostPerScenarioWithoutCostoGopertrial[trial] = sol.get_objective_value() - sol.get_values([self.StartCostToGo])[0] \
                                                                                    * self.SDDPOwner.SetOfSAAScenario[scenario].Probability

                    if Constants.SDDPPrintDebugLPFiles:
                        sol.write("./Temp/bacward_mrpsolution_stage_%d_iter_%d_scenar_%d.sol" % (self.DecisionStage, self.SDDPOwner.CurrentIteration, scenario))

                    self.ImproveCutFromSolution(cut, sol, scenario)
                    if Constants.Debug:
                        print("cur RHS after scenario %s"%(cut.DemandRHS + cut.CapacityRHS + cut.PreviousCutRHS + cut.InitialInventoryRHS))

                    #Average by the number of scenario
                cut.UpdateRHS()
                if Constants.Debug:
                    self.checknewcut(cut, averagecostofthesubproblem,  self.PreviousSDDPStage.Cplex.solution, trial)
                cut.AddCut()
                if Constants.SDDPPrintDebugLPFiles:
                    self.PreviousSDDPStage.Cplex.write("./Temp/PreviousstageWithCut_stage_%d_iter_%d_scenar_%d.lp" % (self.DecisionStage, self.SDDPOwner.CurrentIteration, scenario))
                cutsets.append(cut)
                avgcostssubprob.append(averagecostofthesubproblem)

            return cutsets, avgcostssubprob
            #print("cut added")

    def checknewcut(self, cut, averagecostofthesubproblem, sol, trial, withcorpoint=True):

        currentosttogo = sum(self.SDDPOwner.Stage[t].SAAStageCostPerScenarioWithoutCostoGopertrial[trial]
                             for t in range(self.DecisionStage, len(self.SDDPOwner.StagesSet)))

        avgcorpoint = 0
        avg = 0
        for w in self.SDDPOwner.SAAScenarioNrSet:
            #self.PreviousSDDPStage.UpdateMIPForScenario(w)
            #self.PreviousSDDPStage.Cplex.solve()
            #print("cost from previous stage: %d" %cut.GetCostToGoLBInCUrrentSolution(self.PreviousSDDPStage.Cplex.solution))
            #cut.Print()
            avg += cut.GetCostToGoLBInCUrrentSolution(trial) * self.SDDPOwner.SetOfSAAScenario[w].Probability
            if Constants.GenerateStrongCut and withcorpoint:
                avgcorpoint += cut.GetCostToGoLBInCorePoint(trial) * self.SDDPOwner.SetOfSAAScenario[w].Probability

            #self.PreviousSDDPStage.Cplex.write(
            #    "./Temp/test_previous_stage_%d_iter_%d_scenar_%d.lp" % (
            #    self.DecisionStage, self.PreviousSDDPStage.DecisionStage, w))

        print("Cut added, cost to go with trial sol: %r cost to go corepoint: %r  (actual of backward pass sol: %r, avg of subproblems : %r)" % (
              avg, avgcorpoint, currentosttogo, averagecostofthesubproblem))


    def GetBigMValue(self, p):
        result = self.SDDPOwner.CurrentBigM[p]
        return result

    def IncreaseCutWithFlowDual(self, cut, sol, scenario):
        if Constants.Debug:
            print("Increase cut with flow dual")
        duals = sol.get_dual_values(self.IndexFlowConstraint)

        #print("DUALS flow::::%s" % duals)

        for i in range(len(duals)):
            duals[i]= duals[i] * self.SDDPOwner.SetOfSAAScenario[scenario].Probability
            if duals[i] <> 0:
                p = self.ConcernedProductFlowConstraint[i]
                if not self.IsLastStage():
                    periodproduction = self.GetTimePeriodAssociatedToInventoryVariable(p) - self.Instance.LeadTimes[p]
                else:
                    periodproduction = self.ConcernedTimeFlowConstraint[i] - self.Instance.LeadTimes[p]

                if periodproduction >= 0:
                    cut.IncreaseCoefficientQuantity(p, periodproduction, duals[i])

                if not self.IsLastStage():
                    periodpreviousstock = self.GetTimePeriodAssociatedToInventoryVariable(p) -1
                else:
                    periodpreviousstock = self.ConcernedTimeFlowConstraint[i] - 1

                if periodpreviousstock >= 0:
                    cut.IncreaseCoefficientInventory(p, self.GetTimePeriodAssociatedToInventoryVariable(p) -1, duals[i])
                else:
                    cut.IncreaseInitInventryRHS(-1*duals[i] * self.Instance.StartingInventories[p])

                if self.Instance.HasExternalDemand[p]:
                    cut.IncreaseCoefficientBackorder(p, self.GetTimePeriodAssociatedToBackorderVariable(p) -1, -duals[i])
                    cut.IncreaseDemandRHS(duals[i]
                                          * self.SDDPOwner.SetOfSAAScenario[scenario].Demands[self.GetTimePeriodAssociatedToInventoryVariable(p)][p])

    def IncreaseCutWithProductionDual(self, cut, sol, scenario):
        if Constants.Debug:
                print("Increase cut with production dual")
        duals = sol.get_dual_values(self.IndexProductionQuantityConstraint)
        #print("Duals Production:::%s"%duals)
        for i in range(len(duals)):
            if duals[i] <> 0:
                duals[i] = duals[i] * self.SDDPOwner.SetOfSAAScenario[scenario].Probability
                p = self.ConcernedProductProductionQuantityConstraint[self.IndexProductionQuantityConstraint[i]]
                t = self.ConcernedTimeProductionQuantityConstraint[self.IndexProductionQuantityConstraint[i]]
                cut.IncreaseCoefficientProduction(p, t, -1*self.GetBigMValue(p) * duals[i])


    def IncreaseCutWithCapacityDual(self, cut, sol, scenario):
         if Constants.Debug:
            print("Increase cut with capacity dual")
         duals = sol.get_dual_values(self.IndexCapacityConstraint)
         for i in range(len(duals)):
             if duals[i] <> 0:
                 duals[i] = duals[i] * self.SDDPOwner.SetOfSAAScenario[scenario].Probability
                 k = self.ConcernedResourceCapacityConstraint[i]
                 cut.IncreaseCapacityRHS(self.Instance.Capacity[k] * duals[i])

    def IncreaseCutWithCutDuals(self, cut, sol, scenario):

        #if self.SDDPOwner.CurrentIteration > 0 :
            if Constants.Debug:
                print("Increase cut with cut duals")
            duals = sol.get_dual_values(self.IndexCutConstraint)
            #print("cut duals %s"%duals)
            for i in range(len(duals)):
                if duals[i] <> 0:
                    duals[i] = duals[i] * self.SDDPOwner.SetOfSAAScenario[scenario].Probability
                    c = self.ConcernedCutinConstraint[i]

                    #In the new cut the contribution of C to the RHS is the RHS of C plus the value of of te variable of the current stage.
                    #variableatstage = c.GetCutVariablesAtStage()
                    #valueofvariable = sol.get_values(variableatstage)
                    #coefficientvariableatstage =c.GetCutVariablesCoefficientAtStage()
                    #valueofvarsinconsraint = sum(i[0] * i[1] for i in zip(valueofvariable, coefficientvariableatstage))
                    cut.IncreasePReviousCutRHS(c.GetRHS() * duals[i])#( c.GetRHS() + valueofvarsinconsraint )* duals[i])

                    for tuple in c.NonZeroFixedEarlierProductionVar:
                        p=tuple[0]; t=tuple[1]
                        cut.IncreaseCoefficientProduction(p, t, c.CoefficientProductionVariable[t][p] * duals[i])
                    for tuple in c.NonZeroFixedEarlierQuantityVar:
                        p = tuple[0];                t = tuple[1]
                        cut.IncreaseCoefficientQuantity(p,t, c.CoefficientQuantityVariable[t][p] * duals[i])
                    for tuple in c.NonZeroFixedEarlierBackOrderVar:
                        p = tuple[0];               t = tuple[1]
                        cut.IncreaseCoefficientBackorder(p, t, c.CoefficientBackorderyVariable[t][self.Instance.ProductWithExternalDemandIndex[p]] * duals[i])
                    for tuple in c.NonZeroFixedEarlierStockVar:
                        p = tuple[0];                t = tuple[1]
                        cut.IncreaseCoefficientInventory(p,t, c.CoefficientStockVariable[t][p] * duals[i])

    # Try to use the corepoint method of papadakos, remove if it doesn't work
    # average current solution with last core point
    def UpdateCorePoint(self):
        if self.SDDPOwner.CurrentIteration > 1:
            # Try to use the corepoint method of papadakos, remove if it doesn't work
            if not self.IsLastStage():
                self.CorePointQuantityValues = [[0.5 * self.QuantityValues[w][p] + 0.5 * self.CorePointQuantityValues[w][p]
                                                 for p in self.Instance.ProductSet] for w in self.TrialScenarioNrSet]
            if self.IsFirstStage():
                self.CorePointProductionValue = [[[max(0.5 * self.ProductionValue[w][t][p] + 0.5 * self.CorePointProductionValue[w][t][p], 0.0)
                                                 for p in self.Instance.ProductSet] for t in self.Instance.TimeBucketSet] for w in self.TrialScenarioNrSet]
            # The value of the inventory variables (filled after having solve the MIPs for all scenario)
            productwithstockvariable = self.GetProductWithStockVariable()
            self.CorePointInventoryValue = [[0.5 * self.InventoryValue[w][p] + 0.5 * self.CorePointInventoryValue[w][p]
                                             if p in productwithstockvariable
                                             else 0
                                             for p in self.Instance.ProductSet] for w in self.TrialScenarioNrSet]
            # The value of the backorder variable (filled after having solve the MIPs for all scenario)
            productwithbackorder = self.GetProductWithBackOrderVariable()

            self.CorePointBackorderValue = [[0.5 * self.BackorderValue[w][self.Instance.ProductWithExternalDemandIndex[p]] + 0.5 * self.CorePointBackorderValue[w][self.Instance.ProductWithExternalDemandIndex[p]]
                                                if p in productwithbackorder
                                                else 0
                                             for p in self.Instance.ProductSet]
                                            for w in self.TrialScenarioNrSet]
        else:
            # Try to use the corepoint method of papadakos, remove if it doesn't work
            if not self.IsLastStage():
                self.CorePointQuantityValues = [[self.QuantityValues[w][p]
                                                 for p in self.Instance.ProductSet]
                                                for w in self.TrialScenarioNrSet]
            if self.IsFirstStage():
                self.CorePointProductionValue = [[[self.ProductionValue[w][t][p]
                                                   for p in self.Instance.ProductSet]
                                                  for t in self.Instance.TimeBucketSet]
                                                 for w in self.TrialScenarioNrSet]
            productwithstockvariable = self.GetProductWithStockVariable()
            # The value of the inventory variables (filled after having solve the MIPs for all scenario)
            self.CorePointInventoryValue = [[self.InventoryValue[w][p]
                                             if p in productwithstockvariable
                                             else 0
                                             for p in self.Instance.ProductSet]
                                            for w in self.TrialScenarioNrSet]
            # The value of the backorder variable (filled after having solve the MIPs for all scenario)
            productwithbackorder = self.GetProductWithBackOrderVariable()
            self.CorePointBackorderValue = [[ self.BackorderValue[w][self.Instance.ProductWithExternalDemandIndex[p]]
                                              if p in productwithbackorder
                                              else 0
                                             for p in self.Instance.ProductSet]
                                            for w in self.TrialScenarioNrSet]

    def ChangeSetupToBinary(self):

        indexarray = [self.GetIndexProductionVariable(p, t)
                      for t in self.Instance.TimeBucketSet
                      for p in self.Instance.ProductSet]
        self.Cplex.variables.set_types(zip(indexarray, ["B"]*len(indexarray)))
        self.Cplex.variables.set_lower_bounds(zip(indexarray, [0.0]*len(indexarray)))
        self.Cplex.variables.set_upper_bounds(zip(indexarray, [1.0]*len(indexarray)))

    def ChangeSetupToValueOfTwoStage(self):
        lbtuple=[]
        ubtuples=[]
        for p in self.Instance.ProductSet:
            for t in self.Instance.TimeBucketSet:
                lbtuple.append((self.GetIndexProductionVariable(p, t), self.SDDPOwner.HeuristicSetupValue[t][p]))
                ubtuples.append((self.GetIndexProductionVariable(p, t), self.SDDPOwner.HeuristicSetupValue[t][p]))

        self.Cplex.variables.set_lower_bounds(lbtuple)
        self.Cplex.variables.set_upper_bounds(ubtuples)

    def CreateValideInequalities(self):
        AternativeSet = [self.GenerateAlterantiveComponent([[i]], [[i]]) for i in self.Instance.ProductWithExternalDemand]
        LSet = range(0,4)

        for p in self.Instance.ProductWithExternalDemand:
            for t in self.Instance.TimeBucketSet:
                for O in AternativeSet[p]:
                    for l in LSet:
                        var = [self.GetIndexEstmateCostToGoPerItemPeriod(p, t)]
                        coeff = [1.0]
                        rhs = float(self.Instance.ForecastedAverageDemand[t][p]\
                                    * min(self.Instance.InventoryCosts[i] for i in O) * (l+1))
                        for i in O:
                            leadtime = self.Instance.GetLeadTime(i, p)
                            if t-l-leadtime > 0 and rhs > 0:
                                 for tau in range(t - l - leadtime, t+1):
                                     var = var + [self.GetIndexProductionVariable(i, tau)]
                                     coeff = coeff + [rhs]

                        if len(var) > 1:
                            self.Cplex.linear_constraints.add(lin_expr=[cplex.SparsePair(var, coeff)],
                                                              senses=["G"],
                                                              rhs=[rhs],
                                                              names=["inequality p%r, t%r, O%r L%r" % (p, t, O, l)])
                            self.LastAddedConstraintIndex = self.LastAddedConstraintIndex + 1

        var = [self.StartCostToGo]
        coeff = [1.0]
        for p in self.Instance.ProductWithExternalDemand:
            for t in self.Instance.TimeBucketSet:
                var = var + [self.GetIndexEstmateCostToGoPerItemPeriod(p, t)]
                coeff = coeff + [-1.0]

        self.Cplex.linear_constraints.add(lin_expr=[cplex.SparsePair(var, coeff)],
                                      senses=["G"],
                                      rhs=[0.0],
                                      names=["inequality O:%r l:%r" % (O, l)])

        self.LastAddedConstraintIndex = self.LastAddedConstraintIndex + 1

        # if self.IsFirstStage():
        #     for i in self.Instance.ProductSet:
        #         for t in range(0, 0):#range(self.Instance.NrTimeBucket-4, self.Instance.NrTimeBucket):
        #             var = [self.GetIndexProductionVariable(i, t)]
        #             coeff = [1.0]
        # #            var = var + [self.GetIndexZVariable(i, t, t)]
        # #            coeff = coeff + [-1.0]
        #             self.Cplex.linear_constraints.add(lin_expr=[cplex.SparsePair(var, coeff)],
        #                                               senses=["E"],
        #                                               rhs=[self.SDDPOwner.HeuristicSetupValue[t][i]])
        #             self.LastAddedConstraintIndex = self.LastAddedConstraintIndex + 1

                    #var = [self.GetIndexZVariable(i, t3, t) for t3 in self.Instance.TimeBucketSet]
                    #coeff = [1.0 for t3 in self.Instance.TimeBucketSet]
                    #self.Cplex.linear_constraints.add(lin_expr=[cplex.SparsePair(var, coeff)],
                    #                                  senses=["E"],
                    #                                  rhs=[1.0])
                    #self.LastAddedConstraintIndex = self.LastAddedConstraintIndex + 1

                    #for t2 in self.Instance.TimeBucketSet:
                    #    var =  [self.GetIndexProductionVariable(i, t) ]
                    #    coeff = [-1.0]
                    #    var = var + [self.GetIndexZVariable(i, t, t2)]
                    #    coeff = coeff + [1.0]
                    #    self.Cplex.linear_constraints.add(lin_expr=[cplex.SparsePair(var, coeff)],
                    #                                      senses=["L"],
                    #                                      rhs=[0.0])
                    #    self.LastAddedConstraintIndex = self.LastAddedConstraintIndex + 1

                    #     self.LastAddedConstraintIndex = self.LastAddedConstraintIndex + 1
       # for i in self.Instance.ProductSet:
       #     var = [self.GetIndexProductionVariable(i, t) for t in self.Instance.TimeBucketSet]
       #     coeff = [1.0 for t in self.Instance.TimeBucketSet]
       #     rhs = sum(self.SDDPOwner.HeuristicSetupValue[t][i] for t in self.Instance.TimeBucketSet)
       #     self.Cplex.linear_constraints.add(lin_expr=[cplex.SparsePair(var, coeff)],
       #                                  senses=["G"],
       #                                   rhs=[rhs],
       #                                   names=["constrain setup"])

       #     self.LastAddedConstraintIndex = self.LastAddedConstraintIndex + 1

    #This function is used to generate alternative used to generate cuts
    def GenerateAlterantiveComponent(self, CurrentAlteranitveSet, AlternativeToExpend):
        nextalternates = []
        for alternateset in AlternativeToExpend:
            for i in alternateset:
                parents = [p for p in self.Instance.ProductSet if self.Instance.Requirements[i][p] >= 1]
                for j in parents:
                    alternate = [q for q in self.Instance.ProductSet if self.Instance.Alternates[j][q]]
                    alternate = alternate + [j]
                    nextalternates.append(alternate)

        nextalternates = list(k for k, _ in itertools.groupby(nextalternates))
        CurrentAlteranitveSet = CurrentAlteranitveSet + nextalternates
        if len(nextalternates) == 0:
            return CurrentAlteranitveSet
        else:
            return self.GenerateAlterantiveComponent(CurrentAlteranitveSet, nextalternates)

    def CleanCuts(self):
        for cut in self.ConcernedCutinConstraint:
            if cut.LastIterationWithDual < self.SDDPOwner.CurrentIteration - 100:
                cut.RemoveCut()