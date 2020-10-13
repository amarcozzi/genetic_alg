import time

import matplotlib.pyplot as plt
import numpy as np
from pandas import DataFrame
from scipy.optimize import linprog


class Problem:
    """
        A problem represents a m-dim knapsack problem with m knapsacks, each bound by constraint b_i for i = 1, ..., m
        and n items each with profit p_j and cost r_ij for j = 1, ...., n

        Profits, weights, and bag limits each given by the Chu and Beasley paper

        If you call Problem(n, m, alpha) then it will create an example multi-dimension knapsack problem with n items,
        m knapsacks, and a bag restraint proportional to the tolerance ratio, alpha.

        self.r is an m x n np array representing the multi-dimensional restraints
        self.p is a  1 x n np array representing the profit of each item
        self.b is a  1 x m np array representing the total weight of each knapsack
    """

    def __init__(self, n, m, alpha):
        self.items = n
        self.knapsacks = m
        # Generate the weight (restraint) for i = 1, ..., m knapsacks with j = 1, ..., n items
        self.r = np.random.randint(low=0, high=1000, size=(m, n))
        # Generate bag constraint b_i
        self.b = np.zeros(m)
        self.b = alpha * np.sum(self.r, axis=1)
        self.b = self.b.astype(int)
        # Generate the profit for j = 1, ..., n items
        q = np.random.rand(1, n)
        self.p = np.sum(np.multiply(self.r, 1 / m), axis=0) * q
        self.p = self.p.astype(int)


def initialize_pop(N, ga_problem):
    """
    This function implements Algorithm 2, Initialize P(0) for the MKP
    s.t. P(0) = {S_1, ... , S_N} where S_i in {0, 1}^n

    Each of the initial feasible solutions randomly selects a variable, and sets it to one if the solution is feasible
    :param ga_problem:
    :param N: number of chromosomes to appear in the solution space S
    :return: returns a population, pop, with N chromosomes each reflecting the selection of n items
    """
    # initialize the N x n population with everything set to 0
    S = np.zeros(shape=(N, ga_problem.items), dtype=int)

    # Loop through each k = 1, ..., N possible solutions and randomly add item i to knapsack j,
    # UNLESS doing so violates the r_ij * x_j <= b_i condition
    for k in range(N):
        # initialize restraints on population k
        R = np.zeros(ga_problem.knapsacks, dtype=int)
        R[:] = np.sum(np.multiply(ga_problem.r[:, :], S[k, :]), axis=1)

        # generate list T of all possible j = 1, ..., n items that can exist in S_k
        T = np.arange(ga_problem.items)
        np.random.shuffle(T)

        # Generate list P of all items that have been picked for solution k
        P = list()

        # pop element j from T
        j, T = T[-1], T[:-1]

        # For all the dimensions - add a random element UNLESS it violates the constraint for the current bag
        while S[k, j] == 0 and np.less_equal((R[:] + ga_problem.r[:, j]), ga_problem.b[:]).all():
            S[k, j] = 1
            P.append(j)
            R[:] += ga_problem.r[:, j]
            j, T = T[-1], T[:-1]

        # SANITY CHECK
        for i in range(ga_problem.knapsacks):
            if np.greater(R[:], ga_problem.b[:]).any():
                raise Exception("PROBLEM: fancy alg has a solution that violates a restraint")

    return S


def evaluate_pop_fitness(population, problem):
    """
    This function evaluates population fitness as a function of p_j * x_j
    where problem.p is the profit vector for item j
    and population is a vector where each column j is a 0 or 1 representing if item j is present
    :param population: population with k members with n items each
    :param problem: contains profit vector problem.p
    :return: fitness of each member of the population
    """
    # population has more than 1 solution
    number_solutions = population[:, 0].size
    # initialize fitness function vector
    evaluated_fitness = np.zeros(number_solutions)
    # calculate fitness
    evaluated_fitness[:] = np.sum(np.multiply(problem.p, population[:, :]), axis=1)  # axis=1 implies row-wise sum
    return evaluated_fitness


def evaluate_child_fitness(child, problem):
    """
    This function evaluates the fitness of a single child solution
    :param child: child solution to evaluate fitness
    :param problem: profit array to calculate fitness
    :return: evaluated_fitness: the fitness of the child
    """
    return np.sum(np.multiply(problem.p[:], child[:]))


def binary_tournament_selection(population, tournament_fitness):
    """
    This function performs a binary tournament selection from individuals randomly selected in the population
    Since this is a BINARY tournament selection we pick T = 2 meaning that we randomly select four members of the
    population and put them in sets T1 and T2. The best element in T1 becomes P1, and the best element in T2 becomes
    P2
    :param population:
    :param tournament_fitness:
    :return: parent_1, parent_2 are the ROW indices of the parents 1 and 2 in the population vectors
    """
    # T = 2 was chosen by the authors
    T = 2
    # generate the population pool
    population_pool = np.arange(population[:, 0].size)
    # pick 2 items for T_1
    T_1 = np.random.choice(population_pool, T, replace=False)
    population_pool = np.delete(population_pool, T_1)
    T_2 = np.random.choice(population_pool, T, replace=False)
    # parent_1 is winner of T_1
    parent_1 = T_1[np.argmax(tournament_fitness[T_1])]
    # parent_2 is winner of T_2
    parent_2 = T_2[np.argmax(tournament_fitness[T_2])]

    return parent_1, parent_2


def uniform_crossover(parent_1, parent_2):
    """
    This function applies the uniform crossover function by iterating through all the i bits in the two parents
    a bit b = [0, 1] is randomly selected. For all the bits in the child C, if b = 0 then the ith bit of C is taken
    from parent_1, if b = 1, then the ith bit of C is taken from parent_2
    :param parent_1:
    :param parent_2:
    :return: C: the child of parent_1 and parent_2 where bits are randomly selected from parent_1 or parent_2
    """
    # initialize the child C
    C = np.zeros(parent_1.size, dtype=int)

    # loop through the bits of the parents
    for i in range(parent_1.size):
        b = np.random.randint(2, size=1)
        # if b = 0 make the ith bit of C = ith bit of parent_1
        if b == 0:
            C[i] = parent_1[i]
        # if b = 1 make the ith bit of C = ith bit of parent_2
        else:
            C[i] = parent_2[i]
    return C


def mutate(child):
    """
    This function applies a mutator operation to C.
    Mutator operation: with 50% probability, the operator will flip  a random bit of C
    :param child:
    :return: C: the mutated child
    """
    mutation = np.random.randint(2, size=1)
    # don't apply a mutation
    if mutation == 1:
        return child
    # apply a mutation
    else:
        # pick a bit location to flip
        bit_pool = np.arange(child[:].size)
        i = np.random.choice(bit_pool, 1, replace=False)
        # if child[i] is a 0 make it a 1
        if child[i] == 0:
            child[i] = 1
        else:
            child[i] = 0
        return child


def repair_preprocess(problem):
    """
    This function performs the repair operator preprocessing step as outlined in the paper. It sets the weights w to
    the dual variables of the linear programming problem min: p_j*x_j constrained by r_ij*x*j <= b_j
    then it calculates the utility of each
    :param problem:
    :return: u - utility array of solution S (sorted)
             indices - the index map of the sorted u. so to see how u[i] corresponds to some S[j], j = indices[i]
    """

    b = np.copy(problem.b)
    p = np.copy(problem.p)
    r = np.copy(problem.r)

    c = np.copy(p)  # need to multiply by -1 to convert from finding the largest positive finding smallest negative
    # no need to modify b
    A = np.copy(r)

    dual_c = b
    dual_b = -1.0 * c
    dual_A = -1.0 * np.transpose(A)
    dual_bound = np.zeros((b.size, 2))
    dual_bound[:, 1] = None
    result = linprog(c=-dual_c, A_ub=dual_A, b_ub=dual_b, bounds=dual_bound)
    w = result.x

    denom = 0.0
    for i in range(2):
        denom += np.multiply(w[i], r[i, :])

    u = np.multiply(p, 1 / denom)
    indices = np.argsort(u)
    return indices


def fancy_repair(S, R, problem, u):
    """
    This function implements Algorithm 1 from the Chu and Beasley paper
    :param u: the weighted utility indices
    :param S: The solution to repair
    :param R: The restraints on each bag for solution S
    :param problem: the overall problem constraints
    :return: S: the repaired solution
    """

    # DROP phase
    # if any of those constraints are violated, drop the item with lowest utility until the restraints are met
    # u is ordered in ASCENDING utility so go from left -> right of u
    j = 0
    while np.greater(R[:], problem.b[:]).any():   # this checks if any element in R is > than any element in b
        if S[u[0, j]] == 1:
            S[u[0, j]] = 0
            R[:] -= problem.r[:, u[0, j]]
        j += 1

    # ADD Phase
    # check if we can add any items to the solution without violating any constraints
    # items are considered in decreasing order of utility
    # u is ordered in ASCENDING utility so go from right -> left of u
    for j in range(problem.items - 1, 0, -1):
        if S[u[0, j]] == 0 and np.less_equal((R + problem.r[:, u[0, j]]), problem.b).all():
            S[u[0, j]] = 1
            R[:] += problem.r[:, u[0, j]]

    # SANITY CHECK
    for i in range(problem.knapsacks):
        if np.greater(R[:], problem.b[:]).any():
            raise Exception("PROBLEM: fancy alg has a solution that violates a restraint")

    return S


def repair(S, problem, operator, u):
    """
    This function implements two different repair types to the enforce the resource constraints of the bags
    1) Implements a simple algorithm that sets all the items of an infeasible solution to 0
    2)
    :param u: the weighted utility indices
    :param S: the solution to repair
    :param problem: problem constraints
    :param operator: "simple" or "fancy" depending on which algorithm you'd like to implement
    :return: the repaired solution
    """
    # Initialize R
    R = np.sum(np.multiply(problem.r[:, :], S[:]), axis=1)

    # this is the naive repair operator. It sets the solution to all 0s if it violates any constraints
    if operator == "simple":
        if np.greater(R, problem.b).any():
            S = np.zeros(S.size, dtype=int)
        return S

    # This implements the fancy repair operation
    if operator == "fancy":
        return fancy_repair(S, R, problem, u)

    else:
        raise Exception("repair operator must be either 'simple' or 'fancy'")


def find_ga(k, total_iterations, problem, repair_operator):
    """
    Function implements Algorithm 3: a GA for the MKP from the Chu and Beasley paper
    :param k:   number of solutions to have in the population. Population size never changes, though less fit members
                of the population can be replaced
    :param total_iterations: maximum number of iterations to perform
    :param problem: the problem to find a genetic algorithm solution for. Contains restraint matrix r, profit vector p,
                    and knapsack total restraint vector b. Also has problem.n and problem.m for total number of
                    items and knapsacks respectively
    :param repair_operator: This can be one of two values: "simple" or "fancy"

    :return:    returns two matrices, solution record and fitness record. The last row in each will be the final
                solution and fitness found by the algorithm. The solution at time step i can be found in the ith
                row ith the record
    """
    t = 0
    start = time.time()
    # Initialize population P(0) = {S_1, ..., S_N}, S_i in {0, 1}^n
    population = initialize_pop(k, problem)
    # Evaluate P(0) = {f(S_1), ..., f(S_N)}
    fitness = evaluate_pop_fitness(population, problem)
    # find the weights using LP solver for the fancy repair operator
    u = repair_preprocess(problem)
    # find S* in P(0) s.t. F(S*) > f(S) for all S in P(0).
    # i.e. find the best member of the population
    max_fitness_index = np.argmax(fitness)
    # Keep track of all of our solutions
    solution_record = np.zeros((total_iterations, problem.items))
    fitness_record = np.zeros((total_iterations, 1))
    time_record = np.zeros((total_iterations, 1))
    fitness_record[t, 0] = fitness[max_fitness_index]
    solution_record[t, :] = population[max_fitness_index]
    time_record[t, 0] = time.time() - start
    t += 1

    # now we begin our iterations
    while t < total_iterations:
        start = time.time()
        # carry over the record book from the previous time step
        # update it with the child at the end of the while loop if appropriate
        fitness_record[t, 0] = fitness_record[t - 1, 0]
        solution_record[t, :] = solution_record[t - 1, :]

        # select parents 1 and 2 {P_1, P_2} = phi(P(t)) where phi is our binary tournament selection
        parent_1, parent_2 = binary_tournament_selection(population, fitness)

        # Crossover C = omega(P_1, P_2) where omega is our uniform crossover operation
        C = uniform_crossover(population[parent_1], population[parent_2])

        # Mutate C with our mutation operator
        C = mutate(C)

        # Make C feasible by applying the repair operator
        C = repair(C, problem, repair_operator, u)

        # Make sure there are no duplicate children
        # If C is already in the population - generate a new C
        while C.tolist() in population.tolist():
            parent_1, parent_2 = binary_tournament_selection(population, fitness)
            C = uniform_crossover(population[parent_1], population[parent_2])
            C = mutate(C)
            C = repair(C, problem, repair_operator, u)

        # evaluate f(C)
        C_fitness = evaluate_child_fitness(C, problem)

        # Find member of the population with the lowest fitness and replace it with C
        S_prime = np.argmin(fitness[:])
        if C_fitness > fitness[S_prime]:
            population[S_prime] = C
        # Check of C is the best solution
        if C_fitness > fitness_record[t, 0]:
            fitness_record[t, 0] = C_fitness
            solution_record[t, :] = C

        time_record[t, 0] = time.time() - start
        t += 1

    return fitness_record, solution_record, time_record


def plot_results(data):
    """
    Plot the results of the Genetic Algorithm
    :param data: pandas df with the results
    :return: void - just plots the results
    """
    plt.style.use('seaborn-darkgrid')
    palette = plt.get_cmap('Set1')
    num = 0
    for column in data.drop('x', axis=1):
        num += 1
        plt.plot(data['x'], data[column], marker='', color=palette(num), linewidth=1, alpha=0.9, label=column)
    plt.legend(loc=4, ncol=1, frameon=True)
    plt.xlabel('Iterations')
    plt.ylabel('Fitness')
    plt.show()


if __name__ == '__main__':

    # PROBLEM GENERATION PARAMETERS
    items = 100
    bags = 5
    tightness_ratio = .75

    # Generate the problem
    problem_1 = Problem(items, bags, tightness_ratio)

    # GENETIC ALGORITHM PARAMETERS
    t_max = 10000
    pop_size = 100

    # perform the GA with the simple repair operator
    print("starting work on simple GA")
    fitness_final_naive, solution_final_naive, time_naive = find_ga(pop_size, t_max, problem_1, "simple")
    print("simple solution done")
    print("simple version took ", np.sum(time_naive[:, 0]), " seconds to compute ", t_max, " iterations")
    print("first solution had fitness ", fitness_final_naive[0, 0])
    print("found solution with fitness ", fitness_final_naive[t_max-1, 0])
    print()

    # perform the GA with the fancy repair operator
    print("starting work on fancy GA")
    fitness_final_fancy, solution_final_fancy, time_fancy = find_ga(pop_size, t_max, problem_1, "fancy")
    print("finished with the fancy GA")
    print("fancy version took ", np.sum(time_fancy[:, 0]), " seconds to compute ", t_max, " iterations")
    print("first solution had fitness ", fitness_final_fancy[0, 0])
    print("found solution with fitness ", fitness_final_fancy[t_max - 1, 0])
    print()

    # plot the results
    df = DataFrame({'x': range(t_max), 'naive GA': fitness_final_naive[:, 0],
                       'fancy GA': fitness_final_fancy[:, 0]})
    plot_results(df)
